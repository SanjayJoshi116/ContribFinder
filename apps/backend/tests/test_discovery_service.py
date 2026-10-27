"""Repository discovery job (Phase 4, group 7)."""

import json
import logging
import threading
from datetime import timedelta
from typing import Any, cast

import httpx
import pytest
from django.test import override_settings
from django.utils import timezone

from e2e.builders import add_candidate, make_candidate_repo
from github.models import GitHubAccount
from jobs.models import SyncJob
from repositories.models import (
    CandidateDiscovery,
    Repository,
    RepositoryCandidate,
    RepositoryTopic,
    UserRepository,
)
from services import jobs
from services.discovery.service import DiscoveryService
from services.github.errors import GitHubRateLimited

from .factories import GitHubAccountFactory
from .repo_fixtures import API, mock_repo_api, repo_payload
from .shared_fixtures import developer, make_developer, single_band  # noqa: F401
from .test_github_client import TOKEN

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]

FACTORY_TOKEN = "gho_testtoken0000000000000000000000"


def mock_search(respx_mock, results: dict[str, list[dict[str, Any]]]) -> Any:
    """``results``: query prefix (before the qualifiers) → repository payloads."""

    def respond(request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        for prefix, items in results.items():
            if q.startswith(prefix + " archived:false"):
                return httpx.Response(200, json={"items": items})
        return httpx.Response(200, json={"items": []})

    return respx_mock.get(f"{API}/search/repositories").mock(side_effect=respond)


def new_job(user, **overrides: Any) -> SyncJob:
    fields = {
        "status": "RUNNING",
        "steps": dict.fromkeys(jobs.DISCOVERY_STEPS, "pending"),
        **overrides,
    }
    return SyncJob.objects.create(user=user, job_type="repository_discovery", **fields)


def run(user, **kw) -> SyncJob:
    job = new_job(user)
    DiscoveryService(job, **kw).run()
    SyncJob.objects.filter(pk=job.pk).update(status="COMPLETED")
    job.refresh_from_db()
    return job


HTTPX = repo_payload("encode/httpx", 101)
RICH = repo_payload("Textualize/rich", 102)
TOOL = repo_payload("astral-sh/ruff", 103)


@pytest.fixture
def apis(respx_mock):
    routes = {}
    for payload in (HTTPX, RICH, TOOL):
        routes[payload["full_name"]] = mock_repo_api(
            respx_mock, payload["full_name"], payload["id"]
        )
    return routes


def test_analysis_progress_keeps_metadata_written_meanwhile(
    user, developer, respx_mock, apis, settings, monkeypatch
) -> None:
    from services.repositories.analysis import RepositoryAnalysisService

    settings.DISCOVERY_ANALYSIS_CONCURRENCY = 1
    original = RepositoryAnalysisService.run

    def run_and_write_elsewhere(self, repo_id, *args, **kwargs):
        job = SyncJob.objects.get(user=user, job_type="repository_discovery")
        SyncJob.objects.filter(pk=job.pk).update(metadata={**job.metadata, "other": "kept"})
        return original(self, repo_id, *args, **kwargs)

    monkeypatch.setattr(RepositoryAnalysisService, "run", run_and_write_elsewhere)
    mock_search(respx_mock, {"language:Python": [HTTPX, RICH]})
    job = run(user)
    assert job.metadata["other"] == "kept"  # only changed keys were written over it
    assert len(job.metadata["analyzed"]) == 2


def test_full_run_builds_pool_with_provenance(user, developer, respx_mock, apis) -> None:
    mock_search(
        respx_mock,
        {
            "language:Python": [HTTPX, RICH],
            "topic:developer-tools language:Python": [TOOL, HTTPX],
        },
    )
    job = run(user)

    assert all(state in ("done", "skipped") for state in job.steps.values())
    httpx_candidate = RepositoryCandidate.objects.get(repository__full_name="encode/httpx")
    discoveries = {(d.source, d.query, d.search_rank) for d in httpx_candidate.discoveries.all()}
    assert discoveries == {
        ("language_search", "language:Python", 1),
        ("interest_search", "topic:developer-tools language:Python", 2),
    }
    assert RepositoryCandidate.objects.filter(developer=developer).count() == 3
    assert job.metadata["results_found"] == 4
    assert len(job.metadata["queries_done"]) == 3  # language, interest, interest without language
    assert job.metadata["analysis_outcomes"] == {"analyzed": 3}
    assert set(
        Repository.objects.filter(candidates__isnull=False).values_list("lifecycle", flat=True)
    ) == {"recommendable"}


def test_rediscovery_updates_last_seen_without_duplicates(
    user, developer, respx_mock, apis
) -> None:
    mock_search(respx_mock, {"language:Python": [HTTPX]})
    first = timezone.now() - timedelta(days=3)
    run(user, now=first)
    run(user)
    candidate = RepositoryCandidate.objects.get()
    assert candidate.first_discovered_at == first
    assert candidate.last_seen_at > first
    assert CandidateDiscovery.objects.count() == 1


def test_own_repository_never_a_candidate(user, developer, respx_mock, apis) -> None:
    mine = repo_payload("octocat/mine", 200)
    mock_search(respx_mock, {"language:Python": [mine, HTTPX]})
    job = run(user)
    assert not RepositoryCandidate.objects.filter(repository__full_name="octocat/mine").exists()
    assert job.metadata["rejections"] == {"own_repository": 1}


def test_prefilter_rejections_counted(user, developer, respx_mock, apis) -> None:
    archived = repo_payload("old/archived", 201, archived=True)
    unlicensed = repo_payload("x/unlicensed", 202, license=None)
    mock_search(respx_mock, {"language:Python": [archived, unlicensed, HTTPX]})
    job = run(user)
    assert job.metadata["rejections"] == {"archived": 1, "no_license": 1}
    assert RepositoryCandidate.objects.count() == 1


def test_contributed_repository_is_previously_interacted_and_exempt_from_stars(
    user, developer, respx_mock
) -> None:
    flask = make_candidate_repo(300, "pallets/flask", stars=5)
    UserRepository.objects.create(
        user=user, repository=flask, relation="contributor", merged_pr_count=3
    )
    mock_repo_api(respx_mock, "pallets/flask", 300, stargazers_count=5)
    mock_search(respx_mock, {})
    run(user)
    candidate = RepositoryCandidate.objects.get(repository=flask)
    discovery = candidate.discoveries.get()
    assert (discovery.source, discovery.query, discovery.search_rank) == (
        "previously_interacted",
        "",
        None,
    )
    flask.refresh_from_db()
    assert flask.lifecycle == "recommendable"


def test_retry_resumes_remaining_queries_only(user, developer, respx_mock, apis) -> None:
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"].split(" archived:")[0]
        calls.append(q)
        if q == "topic:developer-tools language:Python" and calls.count(q) == 1:
            return httpx.Response(429, headers={"Retry-After": "30"})
        return httpx.Response(200, json={"items": [HTTPX]})

    respx_mock.get(f"{API}/search/repositories").mock(side_effect=respond)
    job = new_job(user)
    with pytest.raises(GitHubRateLimited):
        DiscoveryService(job).run()
    assert job.steps["search"] == "failed"
    DiscoveryService(job).run()
    assert calls == [
        "language:Python",
        "topic:developer-tools language:Python",
        "topic:developer-tools language:Python",
        "topic:developer-tools",
    ]
    # The yield of the query done before the retry is kept; the others are added once.
    job.refresh_from_db()
    assert set(job.metadata["query_yield"]) == set(job.metadata["queries_done"])
    assert [y["results"] for y in job.metadata["query_yield"].values()] == [1, 1, 1]


def test_invalid_query_skipped(user, developer, respx_mock, apis) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.params["q"].startswith("language:"):
            return httpx.Response(422, json={"message": "Validation Failed"})
        return httpx.Response(200, json={"items": [HTTPX]})

    respx_mock.get(f"{API}/search/repositories").mock(side_effect=respond)
    job = run(user)
    assert job.metadata["queries_skipped"] == ["language:python"]
    assert job.steps["search"] == "done"
    assert RepositoryCandidate.objects.count() == 1
    # Spec: "Refused query in the yield".
    assert job.metadata["query_yield"]["language:python"] == {
        "source": "language_search",
        "band": "",
        "refused": True,
    }


def test_yield_per_query(user, developer, respx_mock, apis) -> None:
    archived = repo_payload("old/archived", 201, archived=True)
    unlicensed = repo_payload("x/unlicensed", 202, license=None)
    mock_search(respx_mock, {"language:Python": [archived, unlicensed, HTTPX, RICH]})
    job = run(user)

    yields = job.metadata["query_yield"]
    assert yields["language:python"] == {
        "source": "language_search",
        "band": "",  # one star band configured (spec: "One star band")
        "results": 4,
        "rejections": {"archived": 1, "no_license": 1},
        "recorded": 2,
    }
    assert set(yields) == set(job.metadata["queries_done"])
    assert all(
        y["results"] == 0 and y["recorded"] == 0
        for k, y in yields.items()
        if k != "language:python"
    )
    # The run totals are unchanged by the per-query record.
    assert job.metadata["rejections"] == {"archived": 1, "no_license": 1}
    assert job.metadata["results_found"] == sum(y["results"] for y in yields.values())
    text = json.dumps(yields)
    assert "archived:false" not in text and "language:Python" not in text  # no query text


def test_sparse_profile_skips_search(user, respx_mock) -> None:
    make_developer(user, skills=(), interests=())
    route = mock_search(respx_mock, {})
    job = run(user)
    assert job.steps["search"] == "skipped"
    assert job.steps["pool"] == "done"
    assert not route.called


def test_fresh_shared_repository_not_refetched(user, developer, respx_mock, apis) -> None:
    mock_search(respx_mock, {"language:Python": [HTTPX]})
    run(user)
    calls_after_first = apis["encode/httpx"]["metadata"].call_count

    other = cast(GitHubAccount, GitHubAccountFactory()).user
    make_developer(other, login="someone")
    run(other)
    assert apis["encode/httpx"]["metadata"].call_count == calls_after_first
    assert RepositoryCandidate.objects.filter(repository__full_name="encode/httpx").count() == 2


@override_settings(DISCOVERY_MAX_ANALYSES_PER_RUN=1)
def test_analysis_cap(user, developer, respx_mock, apis) -> None:
    mock_search(respx_mock, {"language:Python": [HTTPX, RICH, TOOL]})
    job = run(user)
    assert job.metadata["analysis_capped"] is True
    lifecycles = dict(Repository.objects.values_list("full_name", "lifecycle"))
    assert lifecycles == {
        "encode/httpx": "recommendable",  # best search rank goes first
        "Textualize/rich": "discovered",
        "astral-sh/ruff": "discovered",
    }


def test_expired_candidates_removed(user, developer, respx_mock) -> None:
    mock_search(respx_mock, {})
    old = make_candidate_repo(1, lifecycle="recommendable", is_eligible=True)
    recent = make_candidate_repo(2, lifecycle="recommendable", is_eligible=True)
    add_candidate(developer, old, seen=timezone.now() - timedelta(days=31))
    add_candidate(developer, recent, seen=timezone.now() - timedelta(days=29))
    with override_settings(DISCOVERY_MAX_ANALYSES_PER_RUN=0):
        job = run(user)
    assert list(RepositoryCandidate.objects.values_list("repository_id", flat=True)) == [recent.pk]
    # Neither record was found again by this run (no queries), so both are pruned first.
    assert job.metadata["pool_pruned_discoveries"] == 2
    assert job.metadata["pool_expired"] == 1
    assert Repository.objects.filter(pk=old.pk).exists()


@override_settings(DISCOVERY_MAX_POOL=2, DISCOVERY_MAX_ANALYSES_PER_RUN=0)
def test_pool_cap_keeps_best_ranked_interacted_first(user, developer, respx_mock) -> None:
    mock_search(respx_mock, {})
    now = timezone.now()
    this_run = now + timedelta(hours=1)  # records the run "found again": not pruned
    interacted = make_candidate_repo(1)
    worst = make_candidate_repo(2)
    best = make_candidate_repo(3)
    add_candidate(
        developer,
        interacted,
        source="previously_interacted",
        query="",
        rank=None,
        seen=now - timedelta(days=20),
        discovery_seen=this_run,
    )
    add_candidate(developer, worst, rank=25, seen=now, discovery_seen=this_run)
    add_candidate(developer, best, rank=2, seen=now - timedelta(days=5), discovery_seen=this_run)
    job = run(user)
    assert set(RepositoryCandidate.objects.values_list("repository_id", flat=True)) == {
        interacted.pk,
        best.pk,
    }
    assert (job.metadata["pool_evicted"], job.metadata["pool_size"]) == (2, 2)  # + discovery row


def test_token_rejected_fails_job(
    user, developer, respx_mock, django_capture_on_commit_callbacks, caplog
) -> None:
    respx_mock.get(f"{API}/search/repositories").respond(401, json={"message": "Bad credentials"})
    with caplog.at_level(logging.DEBUG), django_capture_on_commit_callbacks(execute=True):
        job, created = jobs.start_discovery(user)
    assert created and job is not None
    job.refresh_from_db()
    assert (job.status, job.error_code) == ("FAILED", "github_auth_invalid")
    stored = f"{job.metadata} {job.error_detail} {job.steps}"
    assert FACTORY_TOKEN not in stored and TOKEN not in stored
    assert FACTORY_TOKEN not in caplog.text


def test_start_discovery_runs_job_to_completion(
    user, developer, respx_mock, apis, django_capture_on_commit_callbacks
) -> None:
    mock_search(respx_mock, {"language:Python": [HTTPX]})
    with django_capture_on_commit_callbacks(execute=True):
        job, _ = jobs.start_discovery(user)
    assert job is not None
    job.refresh_from_db()
    assert job.status == "COMPLETED"
    assert RepositoryCandidate.objects.count() == 1


def test_no_profile_no_job(user) -> None:
    assert jobs.start_discovery(user) == (None, False)
    assert not SyncJob.objects.filter(job_type="repository_discovery").exists()


def test_active_discovery_not_duplicated(user, developer, monkeypatch) -> None:
    monkeypatch.setattr("repositories.tasks.generate_candidates.delay", lambda pk: None)
    first, created = jobs.start_discovery(user)
    again, created_again = jobs.start_discovery(user)
    assert created and not created_again
    assert first == again


class _StubService:
    fail = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def run(self) -> None:
        if self.fail:
            raise GitHubRateLimited("GET /user returned 403", retry_after=99999)


@pytest.mark.parametrize(("fail", "expected"), [(False, 1), (True, 0)])
def test_sync_completion_starts_discovery(
    user, developer, monkeypatch, fail: bool, expected: int
) -> None:
    from github import tasks as github_tasks

    queued: list[int] = []
    monkeypatch.setattr("repositories.tasks.generate_candidates.delay", queued.append)
    monkeypatch.setattr(_StubService, "fail", fail)
    monkeypatch.setattr(github_tasks, "GitHubSyncService", _StubService)
    job = SyncJob.objects.create(user=user, job_type="github_profile_sync", status="PENDING")
    github_tasks.sync_github_profile.delay(job.pk)
    job.refresh_from_db()
    assert job.status == ("FAILED" if fail else "COMPLETED")
    assert SyncJob.objects.filter(job_type="repository_discovery").count() == expected


def test_analysis_completion_starts_discovery(user, developer, monkeypatch) -> None:
    from developers import tasks as developer_tasks

    monkeypatch.setattr("repositories.tasks.generate_candidates.delay", lambda pk: None)
    monkeypatch.setattr(developer_tasks, "ProfileAnalysisService", _StubService)
    job = SyncJob.objects.create(user=user, job_type="profile_analysis", status="PENDING")
    developer_tasks.extract_developer_skills.delay(job.pk)
    assert SyncJob.objects.filter(job_type="repository_discovery").count() == 1


def test_disconnect_cancels_discovery_and_releases_repository(
    user, developer, respx_mock, apis
) -> None:
    mock_search(respx_mock, {"language:Python": [HTTPX]})
    job = new_job(user)

    def cancel_then_respond(request: httpx.Request) -> httpx.Response:
        jobs.cancel_active_syncs(user)  # what the disconnect endpoint does
        return httpx.Response(200, text="# httpx")

    apis["encode/httpx"]["readme"].mock(side_effect=cancel_then_respond)
    from services.errors import JobCancelled

    with pytest.raises(JobCancelled):
        DiscoveryService(job).run()
    job.refresh_from_db()
    assert job.status == "CANCELLED"
    repo = Repository.objects.get(full_name="encode/httpx")
    assert repo.lifecycle == "discovered"
    assert not apis["encode/httpx"]["community"].called


def _metadata_after(barrier: threading.Barrier, payload: dict[str, Any]) -> Any:
    def respond(request: httpx.Request) -> httpx.Response:
        barrier.wait()  # fails unless every repository is being analyzed at the same time
        return httpx.Response(200, json=payload)

    return respond


@pytest.mark.django_db(transaction=True)
@override_settings(DISCOVERY_ANALYSIS_CONCURRENCY=3)
def test_analysis_runs_in_parallel(user, developer, respx_mock, apis) -> None:
    mock_search(respx_mock, {"language:Python": [HTTPX, RICH, TOOL]})
    barrier = threading.Barrier(3, timeout=10)
    for payload in (HTTPX, RICH, TOOL):
        apis[payload["full_name"]]["metadata"].mock(side_effect=_metadata_after(barrier, payload))

    job = run(user)

    assert job.steps["analysis"] == "done"
    assert job.metadata["analysis_outcomes"] == {"analyzed": 3}
    assert len(job.metadata["analyzed"]) == 3
    assert set(Repository.objects.values_list("lifecycle", flat=True)) == {"recommendable"}


@pytest.mark.django_db(transaction=True)
@override_settings(DISCOVERY_ANALYSIS_CONCURRENCY=2)
def test_parallel_failure_keeps_finished_work_and_raises(user, developer, respx_mock, apis) -> None:
    mock_search(respx_mock, {"language:Python": [HTTPX, RICH]})
    apis["Textualize/rich"]["metadata"].mock(
        return_value=httpx.Response(429, headers={"Retry-After": "30"})
    )
    job = new_job(user)

    with pytest.raises(GitHubRateLimited):
        DiscoveryService(job).run()

    job.refresh_from_db()
    assert job.steps["analysis"] == "failed"
    assert job.metadata["analysis_outcomes"] == {"analyzed": 1}
    lifecycles = dict(Repository.objects.values_list("full_name", "lifecycle"))
    assert lifecycles == {"encode/httpx": "recommendable", "Textualize/rich": "discovered"}


def test_banded_run_keeps_both_sizes(user, developer, respx_mock, settings) -> None:
    settings.DISCOVERY_STAR_BANDS = [[20, 999], [1000, None]]
    settings.DISCOVERY_MAX_QUERIES = 20
    settings.DISCOVERY_MAX_POOL = 4
    settings.DISCOVERY_MAX_ANALYSES_PER_RUN = 0
    small = [repo_payload(f"small/p{i}", 500 + i, stargazers_count=100 + i) for i in range(3)]
    large = [repo_payload(f"large/p{i}", 600 + i, stargazers_count=50_000 + i) for i in range(3)]
    requested: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        requested.append(q)
        if not q.startswith("language:Python archived:false"):
            return httpx.Response(200, json={"items": []})
        return httpx.Response(200, json={"items": small if "stars:20..999" in q else large})

    respx_mock.get(f"{API}/search/repositories").mock(side_effect=respond)
    job = run(user)
    python = [q for q in requested if q.startswith("language:Python archived")]
    assert len(python) == 2 and "stars:>=1000" in python[1]
    kept = set(RepositoryCandidate.objects.values_list("repository__full_name", flat=True))
    assert kept == {"small/p0", "small/p1", "large/p0", "large/p1"}  # ranks 1-2 of each band
    assert job.metadata["pool_bands"] == {"below": 0, "20..999": 2, "1000+": 2}
    # One query in both bands: provenance has no star qualifier.
    queries = set(CandidateDiscovery.objects.values_list("query", flat=True))
    assert queries == {"language:Python"}
    yields = job.metadata["query_yield"]
    assert (yields["language:python@0"]["band"], yields["language:python@1"]["band"]) == (
        "20..999",
        "1000+",
    )
    assert yields["language:python@0"]["results"] == 3


def test_contributed_list_rejected_as_not_code(user, developer, respx_mock) -> None:
    books = make_candidate_repo(301, "EbookFoundation/free-programming-books", primary_language="")
    UserRepository.objects.create(user=user, repository=books, relation="contributor")
    mock_search(respx_mock, {})
    job = run(user)
    assert not RepositoryCandidate.objects.filter(repository=books).exists()
    assert job.metadata["rejections"] == {"not_code": 1}


def test_pool_step_removes_lists_found_before_the_rule(user, developer, respx_mock) -> None:
    lists = make_candidate_repo(
        302,
        "public-apis/public-apis",
        lifecycle="recommendable",
        is_eligible=True,
        activity_synced_at=timezone.now(),
        dependencies_synced_at=timezone.now(),  # analyzed: no manifest dependencies
    )
    RepositoryTopic.objects.create(repository=lists, topic="lists")
    code = make_candidate_repo(303, "encode/httpx", lifecycle="recommendable", is_eligible=True)
    add_candidate(developer, lists, rank=1)
    add_candidate(developer, code, rank=2)
    mock_search(respx_mock, {})
    with override_settings(DISCOVERY_MAX_ANALYSES_PER_RUN=0):
        job = run(user)
    assert list(RepositoryCandidate.objects.values_list("repository_id", flat=True)) == [code.pk]
    lists.refresh_from_db()
    assert (lists.is_eligible, lists.ineligible_reason, lists.lifecycle) == (
        False,
        "not_code",
        "indexed",
    )
    assert job.metadata["pool_not_code"] == 1 and job.metadata["pool_size"] == 1


def test_client_error_on_one_repository_does_not_fail_discovery(
    user, developer, respx_mock, apis
) -> None:
    mock_search(respx_mock, {"language:Python": [HTTPX, RICH, TOOL]})
    apis["Textualize/rich"]["metadata"].mock(return_value=httpx.Response(400))
    job = run(user)

    assert job.steps["analysis"] == "done"
    assert job.metadata["analysis_outcomes"] == {"analyzed": 2, "failed": 1}
    rich = Repository.objects.get(full_name="Textualize/rich")
    assert (rich.lifecycle, rich.lifecycle_error) == ("failed", "client_error")
