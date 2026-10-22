"""Discovery and repository data consistency (change discovery-repository-data, batch 7)."""

import threading
from datetime import timedelta
from typing import Any

import httpx
import pytest
from django.db import connections, transaction
from django.test import override_settings
from django.utils import timezone

from core.checks import discovery_config_check
from developers.models import DeveloperInterest, DeveloperSkill
from feedback.models import DismissedRepository, SavedRepository
from repositories.models import (
    CandidateDiscovery,
    Repository,
    RepositoryCandidate,
    RepositoryTopic,
)
from services import jobs
from services.discovery import service as discovery_service
from services.discovery.filters import (
    FilterConfig,
    has_dependencies_annotation,
    prefilter,
)
from services.discovery.queries import configured_star_bands, default_star_bands
from services.discovery.service import DiscoveryService, _band_counts
from services.errors import JobCancelled
from services.github.client import GitHubRepo
from services.github.errors import GitHubNotFound
from services.github.storage import upsert_repository
from services.job_guard import lost_before
from services.repositories import backlog, lifecycle
from services.repositories.analysis import Outcome, RepositoryAnalysisService
from services.repositories.staleness import stale_parts

from .repo_fixtures import (
    API,
    add_candidate,
    expire_parts,
    fresh_repo,
    make_candidate_repo,
    mock_repo_api,
    repo_payload,
)
from .shared_fixtures import developer, public_client, single_band  # noqa: F401
from .test_discovery_service import mock_search, new_job, run

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]


# --- data model (1) ---------------------------------------------------------------------


def test_lifecycle_changed_at_always_set() -> None:
    repo = Repository.objects.create(
        github_id=1,
        owner_login="o",
        name="r",
        full_name="o/r",
        html_url="https://github.com/o/r",
        synced_at=timezone.now(),
    )
    assert repo.lifecycle_changed_at is not None


# --- client (2.1) -------------------------------------------------------------------------


def test_get_repository_by_id(client, respx_mock) -> None:
    respx_mock.get(f"{API}/repositories/42").respond(200, json=repo_payload("new-org/tool", 42))
    repo = client.get_repository_by_id(42)
    assert (repo.github_id, repo.full_name) == (42, "new-org/tool")


def test_get_repository_by_id_not_found(client, respx_mock) -> None:
    respx_mock.get(f"{API}/repositories/42").respond(404, json={"message": "Not Found"})
    with pytest.raises(GitHubNotFound):
        client.get_repository_by_id(42)


# --- names and metadata (2) -----------------------------------------------------------------


def test_new_repository_takes_a_name_without_deleting_the_holder(user, developer) -> None:
    old = fresh_repo(1, "org/tool")
    add_candidate(developer, old)
    SavedRepository.objects.create(user=user, repository=old)
    DismissedRepository.objects.create(user=user, repository=old)

    new = upsert_repository(GitHubRepo.from_api(repo_payload("org/tool", 2)), timezone.now())

    old.refresh_from_db()
    assert new.full_name == "org/tool"
    assert old.full_name == "org/tool~1"
    assert RepositoryCandidate.objects.filter(repository=old).exists()
    assert SavedRepository.objects.filter(repository=old).exists()
    assert DismissedRepository.objects.filter(repository=old).exists()
    assert stale_parts(old, timezone.now()) == ["metadata"]  # due for a lookup by ID
    # Its name and URL are wrong until then: not recommended meanwhile.
    assert (old.lifecycle, old.is_eligible, old.ineligible_reason) == (
        "indexed",
        False,
        "name_released",
    )


def test_released_name_resolved_by_github_id(client, respx_mock, developer) -> None:
    old = fresh_repo(1, "org/tool~1")
    add_candidate(developer, old)
    by_id = respx_mock.get(f"{API}/repositories/1").respond(
        200, json=repo_payload("org/tool-legacy", 1)
    )
    respx_mock.get(f"{API}/repos/org/tool-legacy/languages").respond(200, json={"Go": 10})

    assert RepositoryAnalysisService(client).run(old.pk) == Outcome.ANALYZED

    old.refresh_from_db()
    assert by_id.called
    assert old.full_name == "org/tool-legacy"
    assert RepositoryCandidate.objects.filter(repository=old).exists()


def test_released_name_of_a_deleted_repository_fails(client, respx_mock) -> None:
    old = fresh_repo(1, "org/tool~1")
    respx_mock.get(f"{API}/repositories/1").respond(404, json={"message": "Not Found"})
    assert RepositoryAnalysisService(client).run(old.pk) == Outcome.FAILED
    old.refresh_from_db()
    assert (old.lifecycle, old.lifecycle_error) == ("failed", "not_found")
    assert (old.is_eligible, old.ineligible_reason) == (False, "repository_unavailable")


def test_name_now_belongs_to_another_repository(client, respx_mock) -> None:
    repo = make_candidate_repo(1, "org/tool")
    mock_repo_api(respx_mock, "org/tool-legacy", 1)
    respx_mock.get(f"{API}/repos/org/tool").respond(200, json=repo_payload("org/tool", 2))
    respx_mock.get(f"{API}/repositories/1").respond(200, json=repo_payload("org/tool-legacy", 1))

    assert RepositoryAnalysisService(client).run(repo.pk) == Outcome.ANALYZED

    repo.refresh_from_db()
    assert repo.full_name == "org/tool-legacy"


def test_search_result_is_not_a_metadata_fetch() -> None:
    fetched = timezone.now() - timedelta(hours=13)
    repo = fresh_repo(1, "encode/httpx", synced_at=fetched, stars=10)
    gh = GitHubRepo.from_api(repo_payload("encode/httpx", 1, stargazers_count=900))

    upsert_repository(gh, timezone.now(), metadata_fetched=False)

    repo.refresh_from_db()
    assert (repo.stars, repo.synced_at) == (900, fetched)
    assert "metadata" in stale_parts(repo, timezone.now())
    created = upsert_repository(
        GitHubRepo.from_api(repo_payload("new/repo", 2)), timezone.now(), metadata_fetched=False
    )
    assert created.synced_at is not None


# --- analysis inputs (3) --------------------------------------------------------------------


def test_eligibility_uses_data_stored_during_the_analysis(client, respx_mock) -> None:
    repo = fresh_repo(7, "encode/httpx")
    expire_parts(repo, ["issues"])

    def archived_meanwhile(request: httpx.Request) -> httpx.Response:
        Repository.objects.filter(pk=repo.pk).update(is_archived=True)  # a search stored it
        return httpx.Response(200, json=[])

    respx_mock.get(f"{API}/repos/encode/httpx/issues").mock(side_effect=archived_meanwhile)

    assert RepositoryAnalysisService(client).run(repo.pk, ["issues"]) == Outcome.ANALYZED

    repo.refresh_from_db()
    assert (repo.is_eligible, repo.ineligible_reason, repo.lifecycle) == (
        False,
        "archived",
        "indexed",
    )


def test_failed_retry_for_one_part_checks_every_part(client, respx_mock) -> None:
    repo = make_candidate_repo(
        7,
        "gone/repo",
        lifecycle="failed",
        is_eligible=False,
        ineligible_reason="repository_unavailable",
        lifecycle_changed_at=timezone.now() - timedelta(days=2),
    )
    metadata = respx_mock.get(f"{API}/repos/gone/repo").respond(404, json={"message": "x"})
    respx_mock.get(f"{API}/repositories/7").respond(404, json={"message": "x"})
    readme = respx_mock.get(f"{API}/repos/gone/repo/readme").respond(404, json={"message": "x"})

    assert RepositoryAnalysisService(client).run(repo.pk, ["readme"]) == Outcome.FAILED

    repo.refresh_from_db()
    assert metadata.called and not readme.called
    assert (repo.lifecycle, repo.is_eligible) == ("failed", False)


def test_queued_part_refreshed_meanwhile_changes_nothing(client, respx_mock) -> None:
    changed_at = timezone.now() - timedelta(days=3)
    repo = fresh_repo(7, "encode/httpx", lifecycle_changed_at=changed_at)
    issues = respx_mock.get(f"{API}/repos/encode/httpx/issues").respond(200, json=[])

    assert RepositoryAnalysisService(client).run(repo.pk, ["issues"]) == Outcome.SKIPPED

    repo.refresh_from_db()
    assert not issues.called
    # No transition stamped: freshness does not regenerate anyone's recommendations.
    assert (repo.lifecycle, repo.lifecycle_changed_at) == ("recommendable", changed_at)
    assert repo.claim_token is None


def test_part_no_longer_stale_is_not_fetched(client, respx_mock) -> None:
    repo = fresh_repo(7, "encode/httpx", lifecycle="stale", stale_parts=["issues"])
    issues = respx_mock.get(f"{API}/repos/encode/httpx/issues").respond(200, json=[])

    assert RepositoryAnalysisService(client).run(repo.pk, ["issues"]) == Outcome.ANALYZED

    repo.refresh_from_db()
    assert not issues.called
    assert repo.lifecycle == "recommendable"


def test_name_released_during_the_fetch_discards_it(client, respx_mock) -> None:
    repo = fresh_repo(7, "org/tool")
    expire_parts(repo, ["readme"])

    def renamed_meanwhile(request: httpx.Request) -> httpx.Response:
        lifecycle.release_name("org/tool", 99)  # another repository took the name
        return httpx.Response(200, text="# Someone else's README")

    respx_mock.get(f"{API}/repos/org/tool/readme").mock(side_effect=renamed_meanwhile)

    assert RepositoryAnalysisService(client).run(repo.pk, ["readme"]) == Outcome.SKIPPED

    repo.refresh_from_db()
    assert repo.full_name == "org/tool~7"
    # Released while claimed: restored to INDEXED, ineligible until resolved by GitHub ID.
    assert (repo.lifecycle, repo.is_eligible, repo.ineligible_reason) == (
        "indexed",
        False,
        "name_released",
    )
    assert repo.claim_token is None
    assert not hasattr(repo, "readme") or repo.readme is None


# --- backlog (4) ------------------------------------------------------------------------------


def test_queued_refresh_is_not_queued_twice(developer) -> None:
    now = timezone.now()
    stale = make_candidate_repo(1, lifecycle="stale", lifecycle_changed_at=now)
    add_candidate(developer, stale)

    assert backlog.queue_batch(now) == [(stale.pk, "all")]
    assert backlog.queue_batch(now + timedelta(minutes=15)) == []
    later = now + (now - lost_before(now)) + timedelta(seconds=1)
    assert backlog.queue_batch(later) == [(stale.pk, "all")]


@pytest.mark.django_db(transaction=True)
def test_overlapping_backlog_runs_skip_rows_being_picked(developer) -> None:
    now = timezone.now()
    stale = make_candidate_repo(1, lifecycle="stale", lifecycle_changed_at=now)
    add_candidate(developer, stale)
    locked, release = threading.Event(), threading.Event()

    def other_run() -> None:  # holds the row lock as a concurrent queue_batch would
        try:
            with transaction.atomic():
                Repository.objects.select_for_update().get(pk=stale.pk)
                locked.set()
                release.wait(10)
        finally:
            connections.close_all()

    thread = threading.Thread(target=other_run)
    thread.start()
    try:
        assert locked.wait(10)
        assert backlog.queue_batch(now) == []  # skipped, not waited for
    finally:
        release.set()
        thread.join()
    assert backlog.queue_batch(now) == [(stale.pk, "all")]


def test_completed_analysis_clears_the_queue_stamp(client, respx_mock, developer) -> None:
    repo = make_candidate_repo(7, "encode/httpx", refresh_queued_at=timezone.now())
    mock_repo_api(respx_mock, "encode/httpx", 7)
    assert RepositoryAnalysisService(client).run(repo.pk) == Outcome.ANALYZED
    repo.refresh_from_db()
    assert repo.refresh_queued_at is None


def test_abandoned_claim_ignores_the_queue_stamp(developer) -> None:
    now = timezone.now()
    abandoned = make_candidate_repo(
        1, lifecycle="fetching", claimed_at=now - timedelta(hours=1), refresh_queued_at=now
    )
    add_candidate(developer, abandoned)
    assert backlog.queue_batch(now) == [(abandoned.pk, "all")]


# --- search and provenance (5) ---------------------------------------------------------------


def test_tool_named_like_a_list_is_analyzed_and_eligible(user, developer, respx_mock) -> None:
    lint = repo_payload("sindresorhus/awesome-lint", 401, language="JavaScript")
    mock_search(respx_mock, {"language:Python": [lint]})
    mock_repo_api(
        respx_mock,
        "sindresorhus/awesome-lint",
        401,
        language="JavaScript",
        manifests={"package.json": '{"dependencies": {"remark-lint": "^9"}}'},
    )
    run(user)
    repo = Repository.objects.get(github_id=401)
    assert RepositoryCandidate.objects.filter(repository=repo).exists()
    assert (repo.is_eligible, repo.lifecycle) == (True, "recommendable")


def test_list_without_dependencies_is_decided_once(user, developer, respx_mock) -> None:
    lst = repo_payload("vinta/awesome-python", 402)
    mock_search(respx_mock, {"language:Python": [lst]})
    routes = mock_repo_api(
        respx_mock, "vinta/awesome-python", 402, manifests={"pyproject.toml": "[project]\n"}
    )
    run(user)
    repo = Repository.objects.get(github_id=402)
    assert (repo.is_eligible, repo.ineligible_reason) == (False, "not_code")
    calls = routes["metadata"].call_count

    job = run(user)  # found again: rejected from stored data, not analyzed again

    assert not RepositoryCandidate.objects.filter(repository=repo).exists()
    assert job.metadata["rejections"].get("not_code") == 1
    assert routes["metadata"].call_count == calls


def test_results_stored_in_github_id_order(user, developer, respx_mock, monkeypatch) -> None:
    payloads = [repo_payload(f"o/r{i}", i) for i in (300, 100, 200)]  # rank order
    mock_search(respx_mock, {"language:Python": payloads})
    stored: list[int] = []
    real = upsert_repository

    def record(gh, now, **kw):
        stored.append(gh.github_id)
        return real(gh, now, **kw)

    monkeypatch.setattr(discovery_service, "upsert_repository", record)
    with override_settings(DISCOVERY_MAX_ANALYSES_PER_RUN=0):
        run(user)
    assert stored == [100, 200, 300]
    ranks = dict(
        CandidateDiscovery.objects.values_list("candidate__repository__github_id", "search_rank")
    )
    assert ranks == {300: 1, 100: 2, 200: 3}


def test_repository_crossing_bands_keeps_one_record(user, developer, respx_mock, settings) -> None:
    settings.DISCOVERY_STAR_BANDS = [[20, 999], [1000, None]]
    settings.DISCOVERY_MAX_QUERIES = 20
    settings.DISCOVERY_MAX_ANALYSES_PER_RUN = 0
    grows = repo_payload("o/grows", 501, stargazers_count=900)
    other = repo_payload("o/big", 502, stargazers_count=5000)
    bands: dict[str, list[dict[str, Any]]] = {"small": [grows], "large": []}

    def respond(request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        if not q.startswith("language:Python archived:false"):
            return httpx.Response(200, json={"items": []})
        return httpx.Response(
            200, json={"items": bands["small"] if "stars:20..999" in q else bands["large"]}
        )

    respx_mock.get(f"{API}/search/repositories").mock(side_effect=respond)
    run(user)
    bands.update(small=[], large=[other, {**grows, "stargazers_count": 1200}])
    run(user)

    records = CandidateDiscovery.objects.filter(candidate__repository__github_id=501)
    assert list(records.values_list("query", "search_rank")) == [("language:Python", 2)]


def test_interactions_read_topics_without_extra_queries(
    django_assert_num_queries, developer
) -> None:
    for i in range(3):
        repo = make_candidate_repo(600 + i, f"o/lib{i}")
        RepositoryTopic.objects.create(repository=repo, topic="python")
    rows = list(
        Repository.objects.annotate(has_dependencies=has_dependencies_annotation())
        .prefetch_related("topics")
        .order_by("pk")
    )
    cfg = FilterConfig.from_settings()
    with django_assert_num_queries(0):
        for repo in rows:
            prefilter(repo, login="x", owned=set(), now=timezone.now(), cfg=cfg, check_stars=False)


# --- pool step and analysis plan (6) ---------------------------------------------------------


@override_settings(DISCOVERY_MAX_ANALYSES_PER_RUN=0)
def test_run_without_queries_keeps_provenance(user, developer, respx_mock) -> None:
    DeveloperSkill.objects.filter(profile=developer).delete()  # nothing to search for
    DeveloperInterest.objects.filter(profile=developer).delete()
    repo = fresh_repo(950, "o/kept")
    add_candidate(developer, repo, rank=3)
    job = run(user)
    assert job.steps["search"] == "skipped"
    assert list(CandidateDiscovery.objects.values_list("query", "search_rank")) == [
        ("language:Python", 3)
    ]


@override_settings(DISCOVERY_MAX_ANALYSES_PER_RUN=0)
def test_rejected_query_keeps_its_records(user, developer, respx_mock) -> None:
    repo = fresh_repo(951, "o/kept")
    add_candidate(developer, repo, rank=3)  # found earlier by the Python language search
    respx_mock.get(f"{API}/search/repositories").respond(422, json={"message": "Validation Failed"})
    job = run(user)
    assert "language:python" in job.metadata["queries_skipped"]
    assert list(CandidateDiscovery.objects.values_list("query", "search_rank")) == [
        ("language:Python", 3)
    ]


def test_cancelled_run_writes_nothing_in_the_pool_step(user, developer) -> None:
    stale = make_candidate_repo(952, "o/expired")
    add_candidate(developer, stale, seen=timezone.now() - timedelta(days=60))
    job = new_job(user, status="CANCELLED")
    service = DiscoveryService(job)
    service.profile, service.now = developer, timezone.now()
    with pytest.raises(JobCancelled):
        service._step_pool()
    assert RepositoryCandidate.objects.filter(repository=stale).exists()


def test_same_query_in_two_bands_keeps_the_better_rank(user, developer) -> None:
    repo = make_candidate_repo(953, "o/edge")
    job = new_job(user)
    service = DiscoveryService(job)
    service.profile, service.now = developer, timezone.now()
    service._record(repo, "language_search", "language:Python", 2)  # 20..999 band
    service._record(repo, "language_search", "language:Python", 25)  # 1000+ band, same run
    assert CandidateDiscovery.objects.get().search_rank == 2
    service.now += timedelta(days=1)  # a later run: its rank replaces the old one
    service._record(repo, "language_search", "language:Python", 25)
    assert CandidateDiscovery.objects.get().search_rank == 25


@override_settings(DISCOVERY_MAX_POOL=2)
def test_evicted_candidates_are_not_analyzed(user, developer, respx_mock) -> None:
    payloads = [repo_payload(f"o/r{i}", 700 + i) for i in range(3)]
    mock_search(respx_mock, {"language:Python": payloads})
    for p in payloads[:2]:
        mock_repo_api(respx_mock, p["full_name"], p["id"])  # the third is never requested
    job = run(user)
    states = dict(Repository.objects.values_list("github_id", "lifecycle"))
    assert states == {700: "recommendable", 701: "recommendable", 702: "discovered"}
    assert job.metadata["analysis_total"] == 2


def test_resumed_analysis_keeps_its_plan(user, developer, respx_mock) -> None:
    repos = [make_candidate_repo(800 + i, f"o/p{i}") for i in range(4)]
    for rank, repo in enumerate(repos, start=1):
        add_candidate(developer, repo, rank=rank)
    mock_repo_api(respx_mock, "o/p1", 801)
    steps = dict.fromkeys(jobs.DISCOVERY_STEPS, "done") | {"analysis": "pending"}
    job = new_job(
        user,
        steps=steps,
        metadata={
            "analysis_plan": [repos[0].pk, repos[1].pk],
            "analysis_total": 25,
            "analyzed": [repos[0].pk],
        },
    )
    DiscoveryService(job).run()
    job.refresh_from_db()
    states = dict(Repository.objects.values_list("github_id", "lifecycle"))
    assert states == {800: "discovered", 801: "recommendable", 802: "discovered", 803: "discovered"}
    assert job.metadata["analysis_total"] == 25
    assert job.metadata["analyzed"] == [repos[0].pk, repos[1].pk]


@override_settings(DISCOVERY_MAX_ANALYSES_PER_RUN=0)
def test_pool_step_rechecks_eligibility(user, developer, respx_mock, settings) -> None:
    now = timezone.now()
    settings.DISCOVERY_MAX_PUSH_AGE_DAYS = 90
    aged = fresh_repo(901, "o/aged", pushed_at=now - timedelta(days=120))
    failed_list = make_candidate_repo(
        902,
        "o/awesome-x",
        lifecycle="failed",
        is_eligible=False,
        ineligible_reason="repository_unavailable",
        dependencies_synced_at=now,
        lifecycle_changed_at=now,
    )
    claimed = fresh_repo(
        903,
        "o/claimed",
        lifecycle="refreshing",
        claimed_at=now,
        pushed_at=now - timedelta(days=120),
    )
    for repo in (aged, failed_list, claimed):
        add_candidate(developer, repo, discovery_seen=now + timedelta(hours=1))
    mock_search(respx_mock, {})

    job = run(user)

    aged.refresh_from_db()
    failed_list.refresh_from_db()
    claimed.refresh_from_db()
    assert (aged.lifecycle, aged.is_eligible, aged.ineligible_reason) == (
        "indexed",
        False,
        "inactive",
    )
    assert (failed_list.lifecycle, failed_list.ineligible_reason) == (
        "failed",
        "repository_unavailable",
    )
    assert (claimed.lifecycle, claimed.is_eligible) == ("refreshing", True)
    assert job.metadata["pool_eligibility_changed"] == 1


def test_stale_repository_keeps_stale_when_eligibility_changes() -> None:
    now = timezone.now()
    repo = fresh_repo(904, "o/stale", lifecycle="stale", license_spdx="")
    assert lifecycle.recheck_eligibility([repo.pk], now=now) == 1
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.is_eligible, repo.ineligible_reason) == (
        "stale",
        False,
        "no_license",
    )
    assert lifecycle.recheck_eligibility([repo.pk], now=now) == 0  # unchanged: no write


def test_band_counts_with_a_gap(settings) -> None:
    settings.DISCOVERY_STAR_BANDS = [[20, 99], [200, 999]]
    assert _band_counts([5, 50, 150, 500, 5000]) == {
        "below": 1,
        "20..99": 1,
        "200..999": 1,
        "other": 2,
    }
    assert "other" not in _band_counts([50])


# --- configuration (7) ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("min_stars", "bands"),
    [(50, [[50, 999], [1000, None]]), (1500, [[1500, None]])],
)
def test_default_bands_follow_min_stars(settings, min_stars, bands) -> None:
    assert default_star_bands(min_stars) == bands
    settings.DISCOVERY_MIN_STARS = min_stars
    settings.DISCOVERY_STAR_BANDS = None  # unset: the bands follow the minimum
    settings.DISCOVERY_MAX_QUERIES = 20
    assert configured_star_bands() == bands
    assert [m.id for m in discovery_config_check()] == []


def test_budget_not_a_multiple_of_the_bands_warns(settings) -> None:
    settings.DISCOVERY_STAR_BANDS = [[20, 99], [100, 999], [1000, None]]
    settings.DISCOVERY_MAX_QUERIES = 25
    messages = discovery_config_check()
    assert [m.id for m in messages] == ["core.W003"]
    assert "leaves 1 search request" in messages[0].msg
    settings.DISCOVERY_STAR_BANDS = [[20, 999], [1000, None]]
    settings.DISCOVERY_MAX_QUERIES = 20
    assert discovery_config_check() == []
