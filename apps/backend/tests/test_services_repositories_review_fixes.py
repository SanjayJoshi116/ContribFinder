"""Repository service fixes from the review sweep (Bug_Backlog.md batch 56, change
services-repositories-review-fixes)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import httpx
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from e2e.builders import add_candidate, fresh_repo, make_candidate_repo
from github.models import GitHubProfile
from issues.models import Issue
from jobs.models import SyncJob
from repositories import tasks
from repositories.models import Lifecycle, Repository
from services.github import oauth
from services.github.client import GitHubRepo
from services.github.storage import lock_for_upsert, upsert_repository
from services.github.text import storable, storable_json
from services.jobs import RECOMMENDATIONS
from services.ranking.freshness import due_profiles
from services.repositories import backlog, lifecycle
from services.repositories.analysis import Outcome, RepositoryAnalysisService
from services.repositories.staleness import PART_FIELDS

from .repo_fixtures import (
    API,
    analyze,
    expire_parts,
    issue_payload,
    mock_repo_api,
    repo_payload,
    take_name,
)
from .shared_fixtures import developer, public_client, single_band  # noqa: F401
from .test_github_sync import job, mock_github, run  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]

TOKEN = "gho_ReviewFixesToken00000000000000000000"


@dataclass
class Broker:
    """Refreshes handed to the broker: ``sent`` records them, ``refuses(pk)`` refuses one."""

    sent: list[int] = field(default_factory=list)
    refuses: Callable[[int], bool] = lambda pk: False

    def delay(self, pk: int) -> None:
        if self.refuses(pk):
            raise ConnectionError("broker down")
        self.sent.append(pk)


@pytest.fixture
def broker(settings: Any, monkeypatch: pytest.MonkeyPatch) -> Broker:
    """A worker runs the tasks, through a broker the test controls."""
    settings.CELERY_TASK_ALWAYS_EAGER = False
    b = Broker()
    monkeypatch.setattr(tasks.sync_repository, "delay", b.delay)
    return b


@pytest.fixture
def sent(broker: Broker) -> list[int]:
    return broker.sent


def ascii_json(value: Any) -> str:
    """JSON with every non-ASCII character escaped, as GitHub may send ``\\u0000``/``\\ud800``."""
    return json.dumps(value, ensure_ascii=True)


# --- RS-2: storable GitHub text ----------------------------------------------------------------


def test_storable_removes_nul_and_replaces_unpaired_surrogates() -> None:
    assert storable("Hello\x00World") == "HelloWorld"
    assert storable("bad \ud800 text \udfff") == "bad � text �"
    ordinary = "emoji \U0001f600, accents é, clef \U0001d11e"
    assert storable(ordinary) == ordinary


def test_storable_json_walks_values_keys_and_lists() -> None:
    parsed = json.loads(ascii_json({"k\x00": ["\ud800", {"x": "a\x00b", "n": 3, "t": True}]}))
    assert storable_json(parsed) == {"k": ["�", {"x": "ab", "n": 3, "t": True}]}


def test_raw_readme_without_nul(client, respx_mock) -> None:
    respx_mock.get(f"{API}/repos/org/tool/readme").respond(200, text="# Tool\x00\x00 docs")
    assert client.get_readme("org/tool") == "# Tool docs"


def test_json_strings_cleaned_also_from_the_cache(client, respx_mock) -> None:
    body = ascii_json(repo_payload("org/tool", 1, description="a\x00b", topics=["t\ud800"]))
    route = respx_mock.get(f"{API}/repos/org/tool")
    route.side_effect = [
        httpx.Response(200, text=body, headers={"ETag": '"v1"'}),
        httpx.Response(304),
    ]
    for _ in range(2):  # a fresh 200, then the cached body on a 304
        gh = client.get_repository("org/tool")
        assert (gh.description, gh.topics) == ("ab", ("t�",))
    assert route.call_count == 2


def test_analysis_with_nul_readme_and_surrogate_issue_completes(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    routes = mock_repo_api(respx_mock, "encode/httpx", 7, readme="Hello\x00World")
    routes["issues"].respond(
        200, text=ascii_json([issue_payload(1, title="Crash\x00", body="bad \ud800 text")])
    )

    assert analyze(client, repo) == Outcome.ANALYZED

    repo.refresh_from_db()
    assert repo.readme.content == "HelloWorld"
    issue = Issue.objects.get(repository=repo)
    assert (issue.title, issue.body) == ("Crash", "bad � text")


def test_search_result_with_nul_description_is_stored(client, respx_mock) -> None:
    payload = {"items": [repo_payload("org/tool", 1, description="Fast\x00 tool")]}
    respx_mock.get(url__startswith=f"{API}/search/repositories").respond(
        200, text=ascii_json(payload)
    )

    (gh,) = client.search_repositories("language:python", 10)
    stored = upsert_repository(gh, timezone.now(), metadata_fetched=False)

    assert Repository.objects.get(pk=stored.pk).description == "Fast tool"


def test_profile_sync_with_nul_readme_completes(job, user, respx_mock) -> None:
    mock_github(respx_mock, readme="Python\x00Go")
    run(job)

    job.refresh_from_db()
    assert job.steps["readme"] == "done"
    assert GitHubProfile.objects.get(user=user).profile_readme == "PythonGo"


# --- RS-1: identity before a refresh without metadata ------------------------------------------


def test_issues_refresh_follows_the_repository_not_the_name(client, respx_mock) -> None:
    repo = fresh_repo(1, "org/tool")
    # GitHub ID 1 is now org/tool-legacy; a new, unstored org/tool (GitHub ID 2) took the name.
    legacy = mock_repo_api(respx_mock, "org/tool-legacy", 1, issues=[issue_payload(5)])
    respx_mock.get(f"{API}/repos/org/tool").respond(200, json=repo_payload("org/tool", 2))
    respx_mock.get(f"{API}/repositories/1").respond(200, json=repo_payload("org/tool-legacy", 1))
    other_issues = respx_mock.get(f"{API}/repos/org/tool/issues").respond(
        200, json=[issue_payload(9)]
    )

    assert analyze(client, repo, ["issues"]) == Outcome.ANALYZED

    repo.refresh_from_db()
    assert repo.full_name == "org/tool-legacy"
    assert list(repo.issues.values_list("number", flat=True)) == [5]
    assert legacy["issues"].called and legacy["languages"].called
    assert not other_issues.called


def test_same_repository_fetches_only_the_stale_part(client, respx_mock) -> None:
    repo = fresh_repo(1, "org/tool")
    routes = mock_repo_api(respx_mock, "org/tool", 1, issues=[issue_payload(5)])
    synced_at = repo.synced_at

    assert analyze(client, repo, ["issues"]) == Outcome.ANALYZED

    assert routes["metadata"].call_count == 1  # the identity check
    assert routes["issues"].called
    assert not routes["languages"].called and not routes["readme"].called
    repo.refresh_from_db()
    assert repo.synced_at == synced_at  # metadata not stored as refreshed


def test_name_serving_another_repository_is_asked_once(client, respx_mock) -> None:
    repo = fresh_repo(1, "org/tool")
    mock_repo_api(respx_mock, "org/tool-legacy", 1)
    by_name = respx_mock.get(f"{API}/repos/org/tool").respond(200, json=repo_payload("org/tool", 2))
    by_id = respx_mock.get(f"{API}/repositories/1").respond(
        200, json=repo_payload("org/tool-legacy", 1)
    )

    assert analyze(client, repo, ["readme"]) == Outcome.ANALYZED

    assert (by_name.call_count, by_id.call_count) == (1, 1)  # the identity check's answer kept


def test_rename_seen_by_the_identity_check_is_stored(client, respx_mock) -> None:
    repo = fresh_repo(1, "org/tool")
    routes = mock_repo_api(respx_mock, "org/tool-new", 1)
    # The old name redirects to the renamed repository (followed by the client).
    old_name = respx_mock.get(f"{API}/repos/org/tool").respond(
        200, json=repo_payload("org/tool-new", 1)
    )
    by_id = respx_mock.get(f"{API}/repositories/1").respond(
        200, json=repo_payload("org/tool-new", 1)
    )

    assert analyze(client, repo, ["readme"]) == Outcome.ANALYZED

    repo.refresh_from_db()
    assert repo.full_name == "org/tool-new"
    assert old_name.call_count == 1 and not by_id.called
    assert routes["readme"].called and routes["languages"].called


def test_identity_name_is_storable(respx_mock) -> None:
    body = '{"login": "octo", "id": 1, "name": "Oc\\u0000to \\ud800", "avatar_url": ""}'
    respx_mock.get(f"{API}/user").respond(200, text=body)
    assert oauth.fetch_identity("token").name == "Octo �"


def test_batch_locks_rows_and_name_holders_in_github_id_order(db) -> None:
    fresh_repo(20, "Org/Five")  # holds the name GitHub ID 5 now has
    fresh_repo(10, "org/ten")
    batch = [GitHubRepo.from_api(repo_payload(n, i)) for n, i in [("org/five", 5), ("org/ten", 10)]]

    with CaptureQueriesContext(connection) as queries:
        lock_for_upsert(batch)

    (lock,) = [q["sql"] for q in queries.captured_queries if "FOR UPDATE" in q["sql"]]
    assert "UPPER" in lock
    assert 'ORDER BY "repositories_repository"."github_id" ASC' in lock


def test_readme_refresh_of_a_deleted_repository_fails(client, respx_mock) -> None:
    repo = fresh_repo(1, "org/tool")
    respx_mock.get(f"{API}/repos/org/tool").respond(404, json={"message": "Not Found"})
    respx_mock.get(f"{API}/repositories/1").respond(404, json={"message": "Not Found"})

    assert analyze(client, repo, ["readme"]) == Outcome.FAILED

    repo.refresh_from_db()
    assert (repo.lifecycle, repo.lifecycle_error) == (Lifecycle.FAILED, "not_found")
    assert (repo.is_eligible, repo.ineligible_reason) == (False, "repository_unavailable")


# --- RS-7: a lost claim is not a failure -------------------------------------------------------


def test_reclaimed_analysis_hitting_404_is_skipped(client, respx_mock) -> None:
    repo = fresh_repo(1, "org/tool")
    expire_parts(repo, ["metadata"])
    other = uuid.uuid4()

    def reclaimed_then_gone(request: httpx.Request) -> httpx.Response:
        Repository.objects.filter(pk=repo.pk).update(claim_token=other)  # another worker
        return httpx.Response(404, json={"message": "Not Found"})

    respx_mock.get(f"{API}/repos/org/tool").mock(side_effect=reclaimed_then_gone)
    respx_mock.get(f"{API}/repositories/1").respond(404, json={"message": "Not Found"})

    assert RepositoryAnalysisService(client).run(repo.pk, ["metadata"]) == Outcome.SKIPPED

    repo.refresh_from_db()
    assert (repo.lifecycle, repo.claim_token) == (Lifecycle.REFRESHING, other)


# --- RS-8: entry labels by the issue label rule ------------------------------------------------


@pytest.mark.parametrize(
    ("names", "flags"),
    [
        (("type: good first issue", "contributions welcome"), (True, True)),
        (("good-first-issue 🐣", "Help Wanted"), (True, True)),
        (("bug", "enhancement"), (False, False)),
    ],
)
def test_entry_label_flags_use_issue_label_rule(client, respx_mock, names, flags) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7, labels=names)

    assert analyze(client, repo) == Outcome.ANALYZED

    repo.refresh_from_db()
    assert (repo.has_good_first_issue_label, repo.has_help_wanted_label) == flags


# --- RS-6, RS-10: name release -----------------------------------------------------------------


def test_holder_differing_in_case_is_released(
    developer, sent, django_capture_on_commit_callbacks
) -> None:
    old = fresh_repo(1, "Org/Tool")
    add_candidate(developer, old)

    with django_capture_on_commit_callbacks(execute=True):
        take_name("org/tool", 2)

    old.refresh_from_db()
    assert (old.full_name, old.ineligible_reason) == ("Org/Tool~1", "name_released")
    assert sent == [old.pk]


def test_case_change_of_the_same_repository_releases_nothing(db) -> None:
    fresh_repo(1, "org/Tool")

    stored = take_name("org/tool", 1)

    assert stored.full_name == "org/tool"
    assert Repository.objects.count() == 1


def test_case_insensitive_lookup_has_an_index() -> None:
    assert "repository_full_name_upper_idx" in {i.name for i in Repository._meta.indexes}


def test_holders_locked_in_github_id_order(db) -> None:
    fresh_repo(5, "Org/Tool")
    fresh_repo(3, "ORG/TOOL")

    with CaptureQueriesContext(connection) as queries:
        holders = lifecycle.release_name("org/tool", 9)

    assert len(holders) == 2
    lock = next(q["sql"] for q in queries.captured_queries if "FOR UPDATE" in q["sql"])
    assert 'ORDER BY "repositories_repository"."github_id" ASC' in lock
    names = set(Repository.objects.values_list("full_name", flat=True))
    assert names == {"Org/Tool~5", "ORG/TOOL~3"}


# --- RS-3: a broker refusal never fails the change that released the name ----------------------


def test_refused_send_unmarks_only_that_repository(
    developer, broker, django_capture_on_commit_callbacks
) -> None:
    first, second = fresh_repo(1, "Org/Tool"), fresh_repo(3, "ORG/TOOL")
    for repo in (first, second):
        add_candidate(developer, repo)
    broker.refuses = lambda pk: pk == first.pk

    with django_capture_on_commit_callbacks(execute=True):
        stored = take_name("org/tool", 2)  # no exception reaches the caller

    assert Repository.objects.filter(pk=stored.pk).exists()
    assert broker.sent == [second.pk]
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.refresh_queued_at is None
    assert second.refresh_queued_at is not None


def test_name_changed_path_survives_a_refused_send(
    client, respx_mock, developer, broker, django_capture_on_commit_callbacks
) -> None:
    old = fresh_repo(1, "org/tool", refresh_queued_at=timezone.now())
    add_candidate(developer, old)
    expire_parts(old, ["readme"])
    broker.refuses = lambda pk: True

    def renamed_meanwhile(request: httpx.Request) -> httpx.Response:
        take_name()
        return httpx.Response(200, text="# Someone else's README")

    respx_mock.get(f"{API}/repos/org/tool").respond(200, json=repo_payload("org/tool", 1))
    respx_mock.get(f"{API}/repos/org/tool/readme").mock(side_effect=renamed_meanwhile)

    with django_capture_on_commit_callbacks(execute=True):
        outcome = RepositoryAnalysisService(client).run(old.pk, ["readme"])

    assert outcome == Outcome.SKIPPED
    old.refresh_from_db()
    assert (old.full_name, old.refresh_queued_at) == ("org/tool~1", None)


# --- RS-5: re-check transitions carry the wall clock -------------------------------------------


def test_recheck_stamps_wall_clock_and_freshness_sees_it(developer) -> None:
    long_ago = timezone.now() - timedelta(hours=2)
    repo = fresh_repo(
        1,
        "org/tool",
        is_archived=True,  # ineligible under the rules, still RECOMMENDABLE
        lifecycle_changed_at=long_ago,
        **{field: long_ago for field in PART_FIELDS.values()},
    )
    add_candidate(developer, repo)
    type(developer).objects.filter(pk=developer.pk).update(analyzed_at=long_ago)
    run_started = timezone.now() - timedelta(hours=1)  # the discovery run's reference time
    generation = SyncJob.objects.create(
        user=developer.user, job_type=RECOMMENDATIONS, status="COMPLETED"
    )
    SyncJob.objects.filter(pk=generation.pk).update(
        started_at=timezone.now() - timedelta(minutes=30)  # started after run_started
    )
    before = timezone.now()

    assert lifecycle.recheck_eligibility([repo.pk], now=run_started) == 1

    repo.refresh_from_db()
    assert (repo.lifecycle, repo.ineligible_reason) == (Lifecycle.INDEXED, "archived")
    assert repo.lifecycle_changed_at >= before
    assert developer.pk in [p.pk for p in due_profiles()]


# --- RS-9: mark_stale reads less and groups its updates ----------------------------------------


@pytest.mark.parametrize("stale_rows", [1, 4])
def test_mark_stale_query_count_does_not_grow(developer, stale_rows) -> None:
    for n in range(stale_rows):
        repo = fresh_repo(10 + n, f"org/tool{n}")
        add_candidate(developer, repo)
        expire_parts(repo, ["metadata"])

    with CaptureQueriesContext(connection) as queries:
        assert backlog.mark_stale(timezone.now()) == stale_rows

    assert len(queries.captured_queries) == 2  # one read, one update for the single group
    rows = list(Repository.objects.values_list("lifecycle", "stale_parts"))
    assert rows == [(Lifecycle.STALE, ["metadata"])] * stale_rows
    assert set(Repository.objects.values_list("previous_lifecycle", flat=True)) == {
        Lifecycle.RECOMMENDABLE
    }
