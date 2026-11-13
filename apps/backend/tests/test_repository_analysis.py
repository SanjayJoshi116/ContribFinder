"""Repository analysis, lifecycle, staleness and background refresh (Phase 4, group 6)."""

import base64
from datetime import timedelta
from typing import Any

import pytest
from django.test import override_settings
from django.utils import timezone

from developers.models import DeveloperProfile
from e2e.builders import add_candidate, make_candidate_repo
from repositories import tasks
from repositories.models import Lifecycle, Repository, RepositorySnapshot
from services.github.errors import GitHubRateLimited
from services.repositories.analysis import Outcome, RepositoryAnalysisService
from services.repositories.staleness import PARTS, stale_parts

from .repo_fixtures import API, analyze, mock_repo_api, repo_payload
from .shared_fixtures import public_client  # noqa: F401
from .test_github_client import SECONDARY_MESSAGES
from .test_profiling_manifests import DEEP_PACKAGE_JSON

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]


@pytest.fixture
def profile(user) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


def test_first_analysis_stores_every_part(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7)

    assert analyze(client, repo) == Outcome.ANALYZED

    repo.refresh_from_db()
    assert repo.lifecycle == Lifecycle.RECOMMENDABLE
    assert repo.is_eligible is True
    assert list(repo.languages.values_list("language", flat=True)) == ["Python"]
    assert set(repo.topics.values_list("topic", flat=True)) == {"python", "http"}
    assert repo.readme.content.startswith("# Project")
    assert repo.has_contributing and repo.has_code_of_conduct and repo.has_issue_templates
    assert repo.has_pull_request_template is False
    assert repo.has_good_first_issue_label and repo.has_help_wanted_label
    assert set(repo.dependencies.values_list("name", flat=True)) == {"httpx", "django"}
    snapshot = repo.snapshots.get()
    assert (snapshot.commits_90d, snapshot.contributors, snapshot.prs_merged_90d) == (42, 57, 1)
    assert snapshot.activity_label == "recently_active"
    assert all(
        [
            repo.readme_synced_at,
            repo.community_synced_at,
            repo.dependencies_synced_at,
            repo.activity_synced_at,
        ]
    )
    assert stale_parts(repo, timezone.now()) == []


def test_completion_uses_the_data_it_just_stored(client, respx_mock, monkeypatch) -> None:
    from services.discovery import filters

    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7)

    def not_read(*args, **kwargs):
        raise AssertionError("eligibility read back what the analysis just stored")

    monkeypatch.setattr(filters, "_topics", not_read)
    monkeypatch.setattr(filters, "stored_has_dependencies", not_read)
    assert analyze(client, repo) == Outcome.ANALYZED
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.is_eligible) == (Lifecycle.RECOMMENDABLE, True)


def test_completion_reads_parts_it_did_not_fetch(client, respx_mock) -> None:
    from e2e.builders import fresh_repo
    from repositories.models import RepositoryTopic

    # A list repository analyzed earlier without manifest dependencies: only its README is
    # refreshed now, so topics and dependencies come from the stored rows.
    repo = fresh_repo(8, "acme/awesome-tools")
    RepositoryTopic.objects.create(repository=repo, topic="python")
    mock_repo_api(respx_mock, "acme/awesome-tools", 8)
    assert analyze(client, repo, ["readme"]) == Outcome.ANALYZED
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.ineligible_reason) == (Lifecycle.INDEXED, "not_code")


def test_lifecycle_passes_through_intermediate_states(client, respx_mock, monkeypatch) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7)
    seen: list[str] = []
    original = Repository.save

    def record(self, *args, **kwargs):
        seen.append(self.lifecycle)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Repository, "save", record)
    analyze(client, repo)
    # ANALYZED and INDEXED are passed within the store transaction, never saved on their own.
    assert [s for s in dict.fromkeys(seen) if s != "discovered"] == ["fetching", "recommendable"]


def test_ineligible_repository_ends_indexed_with_reason(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7, license=None)
    analyze(client, repo)
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.is_eligible, repo.ineligible_reason) == (
        "indexed",
        False,
        "no_license",
    )


def test_missing_optional_files_are_not_failures(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(
        respx_mock, "encode/httpx", 7, readme=None, community={}, labels=(), manifests=None
    )
    assert analyze(client, repo) == Outcome.ANALYZED
    repo.refresh_from_db()
    assert repo.lifecycle == Lifecycle.RECOMMENDABLE
    assert not hasattr(repo, "readme") or repo.readme is None
    assert repo.readme_synced_at is not None
    assert repo.has_contributing is False
    assert repo.has_good_first_issue_label is False


def test_not_found_marks_failed_and_ineligible(client, respx_mock, profile) -> None:
    repo = make_candidate_repo(7, "gone/repo")
    add_candidate(profile, repo)
    respx_mock.get(f"{API}/repos/gone/repo").respond(404, json={"message": "Not Found"})
    by_id = respx_mock.get(f"{API}/repositories/7").respond(404, json={"message": "Not Found"})
    assert analyze(client, repo) == Outcome.FAILED
    assert by_id.called  # not under that name: by GitHub ID, which is gone too
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.lifecycle_error) == ("failed", "not_found")
    assert (repo.is_eligible, repo.ineligible_reason) == (False, "repository_unavailable")


def test_rate_limit_restores_previous_state(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    routes = mock_repo_api(respx_mock, "encode/httpx", 7)
    routes["labels"].respond(429, headers={"Retry-After": "60"})
    with pytest.raises(GitHubRateLimited):
        analyze(client, repo)
    repo.refresh_from_db()
    assert repo.lifecycle == Lifecycle.DISCOVERED
    assert not repo.snapshots.exists()


def test_concurrent_claim_refused_and_stale_claim_reclaimed(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx", lifecycle="fetching", claimed_at=timezone.now())
    routes = mock_repo_api(respx_mock, "encode/httpx", 7)
    assert analyze(client, repo) == Outcome.SKIPPED
    assert not routes["metadata"].called

    Repository.objects.filter(pk=repo.pk).update(
        claimed_at=timezone.now() - timedelta(hours=2), previous_lifecycle="discovered"
    )
    assert analyze(client, repo) == Outcome.ANALYZED


def test_claim_uses_wall_clock_not_job_reference_time(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7)
    job_started = timezone.now() - timedelta(hours=2)
    before = timezone.now()
    assert RepositoryAnalysisService(client, now=job_started).run(repo.pk) == Outcome.ANALYZED
    repo.refresh_from_db()
    assert repo.lifecycle_changed_at is not None and repo.lifecycle_changed_at >= before


@override_settings(REPO_README_MAX_BYTES=10)
def test_readme_truncated(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7, readme="x" * 25)
    analyze(client, repo, ["readme"])
    readme = Repository.objects.get(pk=repo.pk).readme
    assert (readme.content, readme.size, readme.truncated) == ("x" * 10, 25, True)


@override_settings(REPO_SNAPSHOT_HISTORY=3)
def test_snapshot_history_trimmed(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7)
    for _ in range(4):
        analyze(client, repo, ["activity"])
    assert RepositorySnapshot.objects.filter(repository=repo).count() == 3


def test_stale_parts_per_data_type() -> None:
    now = timezone.now()
    repo = make_candidate_repo(
        7,
        synced_at=now - timedelta(hours=13),
        readme_synced_at=now - timedelta(days=1),
        community_synced_at=now - timedelta(days=8),
        dependencies_synced_at=now - timedelta(days=1),
        activity_synced_at=now - timedelta(hours=2),
        issues_synced_at=now - timedelta(hours=2),
    )
    assert stale_parts(repo, now) == ["metadata", "community"]
    never = make_candidate_repo(8)
    assert stale_parts(never, now) == list(PARTS)


def test_mark_stale_only_touches_pooled_analyzed_repositories(profile) -> None:
    old = timezone.now() - timedelta(days=30)
    stamps: dict[str, Any] = {
        "synced_at": old,
        "readme_synced_at": old,
        "community_synced_at": old,
        "dependencies_synced_at": old,
        "activity_synced_at": old,
    }
    pooled = make_candidate_repo(1, lifecycle="recommendable", is_eligible=True, **stamps)
    orphan = make_candidate_repo(2, lifecycle="recommendable", is_eligible=True, **stamps)
    fetching = make_candidate_repo(3, lifecycle="fetching", **stamps)
    for repo in (pooled, fetching):
        add_candidate(profile, repo)

    assert tasks.mark_stale_repositories() == 1

    pooled.refresh_from_db()
    assert (pooled.lifecycle, pooled.previous_lifecycle) == ("stale", "recommendable")
    assert pooled.stale_parts == list(PARTS)
    assert pooled.is_eligible is True  # kept while stale
    assert Repository.objects.get(pk=orphan.pk).lifecycle == "recommendable"
    assert Repository.objects.get(pk=fetching.pk).lifecycle == "fetching"


@override_settings(REPO_REFRESH_BATCH=3)
def test_backlog_selects_due_pooled_repositories(profile, monkeypatch) -> None:
    now = timezone.now()
    queued: list[tuple[str, int]] = []
    monkeypatch.setattr(tasks.sync_repository, "delay", lambda pk: queued.append(("all", pk)))
    monkeypatch.setattr(
        tasks.sync_repository_readme, "delay", lambda pk: queued.append(("readme", pk))
    )
    stale = make_candidate_repo(
        1,
        lifecycle="stale",
        stale_parts=["metadata", "activity"],
        lifecycle_changed_at=now - timedelta(hours=3),
    )
    readme_only = make_candidate_repo(
        2, lifecycle="stale", stale_parts=["readme"], lifecycle_changed_at=now - timedelta(hours=2)
    )
    waiting = make_candidate_repo(
        3, lifecycle="discovered", lifecycle_changed_at=now - timedelta(minutes=30)
    )
    fresh = make_candidate_repo(4, lifecycle="discovered", lifecycle_changed_at=now)
    failed_due = make_candidate_repo(
        5, lifecycle="failed", lifecycle_changed_at=now - timedelta(days=2)
    )
    failed_recent = make_candidate_repo(
        6, lifecycle="failed", lifecycle_changed_at=now - timedelta(hours=1)
    )
    abandoned = make_candidate_repo(
        8,
        lifecycle="fetching",
        lifecycle_changed_at=now - timedelta(minutes=1),
        claimed_at=now - timedelta(hours=1),
    )
    in_progress = make_candidate_repo(
        9, lifecycle="refreshing", lifecycle_changed_at=now - timedelta(days=5), claimed_at=now
    )
    for repo in (stale, readme_only, waiting, fresh, failed_due, failed_recent):
        add_candidate(profile, repo)
    add_candidate(profile, abandoned)
    add_candidate(profile, in_progress)
    make_candidate_repo(7, lifecycle="stale", lifecycle_changed_at=now - timedelta(days=9))

    assert tasks.process_repository_backlog() == 3
    # Oldest first, capped at the batch size; the orphan (7) is never selected.
    assert queued == [("all", failed_due.pk), ("all", stale.pk), ("readme", readme_only.pk)]

    queued.clear()
    with override_settings(REPO_REFRESH_BATCH=50):
        tasks.process_repository_backlog()
    # The first batch is queued already and not queued twice.
    assert {pk for _, pk in queued} == {
        waiting.pk,
        abandoned.pk,  # a dead worker's claim; the live one (9) is left alone
    }


@override_settings(GITHUB_CLIENT_ID="", GITHUB_CLIENT_SECRET="")
def test_backlog_is_a_no_op_without_app_credentials(profile, caplog) -> None:
    add_candidate(profile, make_candidate_repo(1, lifecycle="stale"))
    assert tasks.process_repository_backlog() == 0
    assert "client credentials are not configured" in caplog.text


def test_refresh_fetches_only_stale_parts_with_app_credentials(respx_mock, monkeypatch) -> None:
    def no_user_tokens(*args, **kwargs):
        raise AssertionError("a user token was decrypted")

    monkeypatch.setattr("services.github.client.decrypt_token", no_user_tokens)
    now = timezone.now()
    repo = make_candidate_repo(
        7,
        "encode/httpx",
        lifecycle="stale",
        previous_lifecycle="recommendable",
        is_eligible=True,
        synced_at=now - timedelta(hours=13),
        readme_synced_at=now,
        community_synced_at=now,
        dependencies_synced_at=now,
        activity_synced_at=now - timedelta(days=2),
        issues_synced_at=now,
    )
    routes = mock_repo_api(respx_mock, "encode/httpx", 7)

    tasks.sync_repository.delay(repo.pk)

    repo.refresh_from_db()
    assert repo.lifecycle == Lifecycle.RECOMMENDABLE
    assert routes["metadata"].called and routes["commits"].called
    for part in ("readme", "community", "labels", "contents", "issues"):
        assert not routes[part].called, part
    expected = base64.b64encode(b"test-client-id:test-client-secret").decode()
    assert routes["metadata"].calls.last.request.headers["Authorization"] == f"Basic {expected}"


def test_failed_repository_retry_rechecks_everything(respx_mock) -> None:
    now = timezone.now()
    repo = make_candidate_repo(
        7,
        "encode/httpx",
        lifecycle="failed",
        is_eligible=False,
        ineligible_reason="repository_unavailable",
        readme_synced_at=now,
        community_synced_at=now,
        dependencies_synced_at=now,
        activity_synced_at=now,
    )
    routes = mock_repo_api(respx_mock, "encode/httpx", 7)
    tasks.sync_repository.delay(repo.pk)
    repo.refresh_from_db()
    assert routes["readme"].called and routes["metadata"].called
    assert (repo.lifecycle, repo.is_eligible) == ("recommendable", True)


def test_readme_task_fetches_only_readme(respx_mock) -> None:
    now = timezone.now()
    repo = make_candidate_repo(
        7, "encode/httpx", lifecycle="stale", is_eligible=True, activity_synced_at=now
    )
    routes = mock_repo_api(respx_mock, "encode/httpx", 7)
    tasks.sync_repository_readme.delay(repo.pk)
    assert routes["readme"].called
    assert routes["metadata"].call_count == 1  # the identity check, not a metadata fetch
    assert not routes["languages"].called
    assert Repository.objects.get(pk=repo.pk).lifecycle == "recommendable"


def test_refresh_retries_on_rate_limit_and_releases(respx_mock, monkeypatch) -> None:
    repo = make_candidate_repo(
        7, "encode/httpx", lifecycle="stale", is_eligible=True, previous_lifecycle="recommendable"
    )
    respx_mock.get(f"{API}/repos/encode/httpx").respond(429, headers={"Retry-After": "30"})
    retries: list[int] = []

    class Retried(Exception):
        pass

    def fake_retry(*, countdown):
        retries.append(countdown)
        return Retried()

    monkeypatch.setattr(tasks.sync_repository, "retry", fake_retry)
    with pytest.raises(Retried):
        tasks.sync_repository(repo.pk)
    assert retries and retries[0] >= 30
    assert Repository.objects.get(pk=repo.pk).lifecycle == "stale"


# --- github-error-resilience: repository-specific errors stay with the repository ------------


def test_unexpected_client_error_marks_failed(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "odd/repo")
    respx_mock.get(f"{API}/repos/odd/repo").respond(400, json={"message": "Bad"})
    assert analyze(client, repo) == Outcome.FAILED
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.lifecycle_error) == ("failed", "client_error")
    assert (repo.is_eligible, repo.ineligible_reason) == (False, "repository_unavailable")


def test_uninterpretable_response_marks_failed(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    routes = mock_repo_api(respx_mock, "encode/httpx", 7)
    payload = repo_payload("encode/httpx", 7)
    del payload["id"]
    routes["metadata"].respond(200, json=payload)
    assert analyze(client, repo) == Outcome.FAILED
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.lifecycle_error) == ("failed", "invalid_response")


def test_legal_block_keeps_unavailable_code(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "dmca/repo")
    respx_mock.get(f"{API}/repos/dmca/repo").respond(451)
    assert analyze(client, repo) == Outcome.FAILED
    assert Repository.objects.get(pk=repo.pk).lifecycle_error == "unavailable"


def test_secondary_limit_releases_instead_of_failing(client, respx_mock) -> None:
    repo = make_candidate_repo(
        7, "encode/httpx", lifecycle="stale", is_eligible=True, previous_lifecycle="recommendable"
    )
    routes = mock_repo_api(respx_mock, "encode/httpx", 7)
    routes["contributors"].respond(
        403, json={"message": SECONDARY_MESSAGES[0]}, headers={"X-RateLimit-Remaining": "4000"}
    )
    with pytest.raises(GitHubRateLimited):
        analyze(client, repo, ["activity"])
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.is_eligible, repo.lifecycle_error) == ("stale", True, "")
    assert not repo.snapshots.exists()


def test_renamed_repository_is_followed(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "old-org/tool")
    respx_mock.get(f"{API}/repos/old-org/tool").respond(
        301, headers={"Location": f"{API}/repositories/7"}
    )
    mock_repo_api(respx_mock, "new-org/tool", 7)
    respx_mock.get(f"{API}/repositories/7").respond(200, json=repo_payload("new-org/tool", 7))
    assert analyze(client, repo) == Outcome.ANALYZED
    repo.refresh_from_db()
    assert (repo.github_id, repo.full_name, repo.lifecycle) == (7, "new-org/tool", "recommendable")


def test_programming_error_still_propagates(client, respx_mock, monkeypatch) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7)

    def broken(full_name: str) -> dict[str, int]:
        raise AttributeError("bug")

    monkeypatch.setattr(client, "get_languages", broken)
    with pytest.raises(AttributeError):
        analyze(client, repo)
    assert Repository.objects.get(pk=repo.pk).lifecycle == Lifecycle.DISCOVERED


def test_deeply_nested_candidate_manifest_is_not_a_failure(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7, manifests={"package.json": DEEP_PACKAGE_JSON})
    assert analyze(client, repo) == Outcome.ANALYZED
    repo.refresh_from_db()
    assert set(repo.dependencies.values_list("name", flat=True)) == {"httpx", "django"}


@override_settings(SYNC_MAX_ATTEMPTS=1, REPO_REFRESH_RETRY_MINUTES=60)
def test_refresh_failure_is_recorded_and_delays_the_backlog(
    respx_mock, profile, monkeypatch
) -> None:
    now = timezone.now()
    repo = make_candidate_repo(
        7,
        "encode/httpx",
        lifecycle="stale",
        is_eligible=True,
        stale_parts=["metadata"],
        synced_at=now - timedelta(hours=13),
        lifecycle_changed_at=now - timedelta(hours=1),
    )
    add_candidate(profile, repo)
    respx_mock.get(f"{API}/repos/encode/httpx").respond(503)

    tasks.sync_repository.delay(repo.pk)

    repo.refresh_from_db()
    assert (repo.lifecycle, repo.is_eligible) == ("stale", True)
    assert repo.lifecycle_error == "github_unavailable"
    assert repo.refresh_failed_at is not None
    assert repo.lifecycle_changed_at == now - timedelta(hours=1)

    queued: list[int] = []
    monkeypatch.setattr(tasks.sync_repository, "delay", queued.append)
    assert tasks.process_repository_backlog() == 0

    Repository.objects.filter(pk=repo.pk).update(refresh_failed_at=now - timedelta(minutes=61))
    assert tasks.process_repository_backlog() == 1
    assert queued == [repo.pk]

    respx_mock.reset()
    mock_repo_api(respx_mock, "encode/httpx", 7)
    monkeypatch.undo()
    tasks.sync_repository.delay(repo.pk)
    repo = Repository.objects.get(pk=repo.pk)
    assert (repo.lifecycle, repo.lifecycle_error) == ("recommendable", "")
    assert repo.refresh_failed_at is None


def test_refresh_failure_leaves_claimed_and_failed_repositories_alone() -> None:
    from services.repositories.lifecycle import record_refresh_failure

    claimed = make_candidate_repo(1, lifecycle="refreshing", claimed_at=timezone.now())
    failed = make_candidate_repo(2, lifecycle="failed", lifecycle_error="not_found")
    since = timezone.now()
    record_refresh_failure(claimed.pk, "github_unavailable", since=since)
    record_refresh_failure(failed.pk, "github_unavailable", since=since)
    claimed.refresh_from_db()
    failed.refresh_from_db()
    assert (claimed.lifecycle_error, claimed.refresh_failed_at) == ("", None)
    assert (failed.lifecycle_error, failed.refresh_failed_at) == ("not_found", None)


def test_refresh_delay_applies_only_to_refreshes(profile, monkeypatch) -> None:
    now = timezone.now()
    due = make_candidate_repo(1, lifecycle="failed", lifecycle_changed_at=now - timedelta(days=2))
    recent = make_candidate_repo(
        2, lifecycle="failed", lifecycle_changed_at=now - timedelta(hours=1)
    )
    # A refresh failed, then another run claimed it and its worker died: recover it now.
    abandoned = make_candidate_repo(
        3, lifecycle="refreshing", claimed_at=now - timedelta(hours=1), refresh_failed_at=now
    )
    waiting = make_candidate_repo(4, lifecycle="stale", refresh_failed_at=now)
    for repo in (due, recent, abandoned, waiting):
        add_candidate(profile, repo)
    queued: list[int] = []
    monkeypatch.setattr(tasks.sync_repository, "delay", queued.append)
    assert tasks.process_repository_backlog() == 2
    assert set(queued) == {due.pk, abandoned.pk}


def test_refresh_failure_skips_repository_changed_since() -> None:
    from services.repositories.lifecycle import record_refresh_failure

    now = timezone.now()
    # Another run completed it after this refresh started: its fresh state stays clean.
    redone = make_candidate_repo(1, lifecycle="recommendable", lifecycle_changed_at=now)
    stale = make_candidate_repo(2, lifecycle="stale", lifecycle_changed_at=now - timedelta(hours=1))
    since = now - timedelta(minutes=1)
    record_refresh_failure(redone.pk, "github_unavailable", since=since)
    record_refresh_failure(stale.pk, "github_unavailable", since=since)
    redone.refresh_from_db()
    stale.refresh_from_db()
    assert (redone.lifecycle_error, redone.refresh_failed_at) == ("", None)
    assert stale.lifecycle_error == "github_unavailable" and stale.refresh_failed_at is not None


def test_rejected_app_credentials_record_the_refresh_failure(respx_mock) -> None:
    repo = make_candidate_repo(
        7,
        "encode/httpx",
        lifecycle="stale",
        is_eligible=True,
        previous_lifecycle="recommendable",
        stale_parts=["metadata"],
        lifecycle_changed_at=timezone.now() - timedelta(hours=1),
    )
    respx_mock.get(f"{API}/repos/encode/httpx").respond(401)
    tasks.sync_repository.delay(repo.pk)
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.is_eligible) == ("stale", True)
    assert repo.lifecycle_error == "github_auth_invalid"
    assert repo.refresh_failed_at is not None


def test_error_outside_the_client_propagates(client, respx_mock, monkeypatch) -> None:
    """Only GitHub answers the client can't read are ``invalid_response``: a TypeError in
    ContribFinder's own code is a bug, not a repository failure."""
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7)

    def broken(*args, **kwargs):
        raise TypeError("bug")

    monkeypatch.setattr("services.repositories.analysis.read_manifests", broken)
    with pytest.raises(TypeError):
        analyze(client, repo)
    assert Repository.objects.get(pk=repo.pk).lifecycle == Lifecycle.DISCOVERED


# --- setup facts (change setup-readiness) -----------------------------------------------------

SETUP_FIELDS = ("has_ci", "has_tests", "has_dev_environment", "has_docker_compose")


def setup_facts(repo: Repository) -> tuple[bool | None, ...]:
    repo.refresh_from_db()
    return tuple(getattr(repo, f) for f in SETUP_FIELDS)


def test_setup_facts_found(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    routes = mock_repo_api(
        respx_mock,
        "encode/httpx",
        7,
        root=(".github/", "tests/", ".devcontainer/", "docker-compose.yml"),
        workflows=("ci.yml",),
    )
    assert analyze(client, repo) == Outcome.ANALYZED
    assert setup_facts(repo) == (True, True, True, True)
    assert routes["contents"].call_count == 1  # one root listing for manifests and setup


def test_nothing_found_makes_no_workflows_request(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7, root=("README.md", "main.go"))
    assert analyze(client, repo) == Outcome.ANALYZED
    assert setup_facts(repo) == (False, False, False, False)
    assert not [c for c in respx_mock.calls if c.request.url.path.endswith("/workflows")]


@pytest.mark.parametrize("workflows", [None, ("README.md",)])
def test_github_dir_without_workflow_files_is_not_ci(client, respx_mock, workflows) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    routes = mock_repo_api(respx_mock, "encode/httpx", 7, root=(".github/",), workflows=workflows)
    assert analyze(client, repo) == Outcome.ANALYZED
    assert setup_facts(repo)[0] is False
    assert routes["workflows"].called


def test_other_ci_skips_the_workflows_request(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    routes = mock_repo_api(
        respx_mock, "encode/httpx", 7, root=(".github/", ".travis.yml"), workflows=()
    )
    assert analyze(client, repo) == Outcome.ANALYZED
    assert setup_facts(repo)[0] is True
    assert not routes["workflows"].called


def test_setup_facts_refresh_only_with_dependencies(client, respx_mock) -> None:
    from e2e.builders import fresh_repo

    repo = fresh_repo(8, "acme/tool")
    assert setup_facts(repo) == (None, None, None, None)  # analyzed before setup facts existed
    mock_repo_api(respx_mock, "acme/tool", 8, root=("tests/",))
    assert analyze(client, repo, ["activity"]) == Outcome.ANALYZED
    assert setup_facts(repo) == (None, None, None, None)
    assert analyze(client, repo, ["dependencies"]) == Outcome.ANALYZED
    assert setup_facts(repo) == (False, True, False, False)


def test_no_scoring_code_reads_setup_facts() -> None:
    # Spec: setup facts are never used by a signal, reason, filter or evaluation dataset.
    from pathlib import Path

    import services

    root = Path(services.__file__).parent
    readers = [
        str(path.relative_to(root))
        for folder in ("matching", "ranking", "evaluation", "discovery")
        for path in (root / folder).rglob("*.py")
        if any(field in path.read_text(encoding="utf-8") for field in SETUP_FIELDS)
    ]
    assert readers == []
