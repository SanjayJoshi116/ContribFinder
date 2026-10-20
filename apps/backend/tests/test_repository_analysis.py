"""Repository analysis, lifecycle, staleness and background refresh (Phase 4, group 6)."""

import base64
from datetime import timedelta
from typing import Any

import pytest
from django.test import override_settings
from django.utils import timezone

from developers.models import DeveloperProfile
from repositories import tasks
from repositories.models import Lifecycle, Repository, RepositorySnapshot
from services.github.client import GitHubClient
from services.github.errors import GitHubRateLimited
from services.repositories.analysis import Outcome, RepositoryAnalysisService
from services.repositories.staleness import PARTS, stale_parts

from .repo_fixtures import API, add_candidate, make_candidate_repo, mock_repo_api
from .test_github_client import TOKEN

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]


@pytest.fixture
def profile(user) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


@pytest.fixture
def client():
    with GitHubClient(TOKEN, cache_scope="public") as c:
        yield c


def analyze(client, repo: Repository, parts=None) -> Outcome:
    return RepositoryAnalysisService(client).run(repo.pk, parts)


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
    assert analyze(client, repo) == Outcome.FAILED
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
    assert {pk for _, pk in queued} == {
        stale.pk,
        readme_only.pk,
        waiting.pk,
        failed_due.pk,
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
    assert not routes["metadata"].called
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
