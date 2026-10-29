"""Issue ingestion as a repository analysis part (Phase 7, groups 1 and 4)."""

from datetime import timedelta
from typing import Any, cast

import httpx
import pytest
from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from accounts.models import User
from core.checks import discovery_config_check, issue_config_check
from developers.models import DeveloperProfile
from e2e.builders import add_candidate, fresh_repo, make_candidate_repo
from issues.models import Issue
from repositories import tasks
from repositories.models import Repository
from services.github.client import IssueData, IssuePage
from services.github.errors import GitHubTransientError
from services.repositories.analysis import Outcome, merge_issue_pages
from services.repositories.staleness import stale_parts

from .checks_helpers import ids
from .factories import UserFactory
from .repo_fixtures import API, analyze, expire_parts, issue_payload, mock_repo_api
from .shared_fixtures import public_client  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]

ISSUES = f"{API}/repos/encode/httpx/issues"


@pytest.fixture
def profile(user) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


def pull_request(number: int) -> dict[str, Any]:
    return issue_payload(number, pull_request={"url": "x"})


def test_new_repository_analysis_stores_analyzed_issues(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    issues = [
        issue_payload(
            1,
            title="Fix typo in Django docs",
            body="Short.",
            labels=[{"name": "kind/docs"}, {"name": "good-first-issue"}],
        ),
        issue_payload(2, title="Crash on startup", labels=[{"name": "Type: Bug"}]),
        pull_request(3),
    ]
    routes = mock_repo_api(respx_mock, "encode/httpx", 7, issues=issues)

    assert analyze(client, repo) == Outcome.ANALYZED

    assert routes["issues"].called
    repo.refresh_from_db()
    assert repo.issues_synced_at is not None and repo.issues_truncated is False
    stored = {i.number: i for i in Issue.objects.filter(repository=repo)}
    assert set(stored) == {1, 2}  # the pull request is not an issue
    docs = stored[1]
    assert docs.raw_labels == ["kind/docs", "good-first-issue"]
    assert docs.labels == ["good_first_issue", "documentation"]
    assert docs.contribution_type == "documentation"
    assert docs.contribution_type_evidence["by"] == "label"
    assert docs.difficulty == "beginner"
    assert docs.technologies == [{"slug": "django", "source": "title"}]
    assert docs.analyzed_at is not None
    assert stored[2].contribution_type == "bug_fix"
    assert stale_parts(repo, timezone.now()) == []


@override_settings(ISSUE_BODY_MAX_CHARS=10)
def test_body_is_capped(client, respx_mock) -> None:
    repo = fresh_repo(issues_synced_at=None)
    respx_mock.get(ISSUES).respond(200, json=[issue_payload(1, body="0123456789abcdef")])
    analyze(client, repo, ["issues"])
    assert Issue.objects.get().body == "0123456789"


def test_truncation_recorded(client, respx_mock) -> None:
    repo = fresh_repo(issues_synced_at=None)
    respx_mock.get(ISSUES).respond(
        200, json=[issue_payload(1)], headers={"Link": f'<{ISSUES}?page=2>; rel="next"'}
    )
    analyze(client, repo, ["issues"])
    repo.refresh_from_db()
    assert repo.issues_truncated is True
    assert Issue.objects.count() == 1


def test_refresh_replaces_the_issue_set(client, respx_mock) -> None:
    repo = fresh_repo()
    respx_mock.get(ISSUES).respond(200, json=[issue_payload(1), issue_payload(2)])
    analyze(client, repo, ["issues"])
    kept = Issue.objects.get(number=1)

    respx_mock.get(ISSUES).respond(
        200, json=[issue_payload(1, title="Renamed", labels=[{"name": "bug"}])]
    )
    analyze(client, repo, ["issues"])

    assert list(Issue.objects.values_list("number", flat=True)) == [1]  # #2 was closed
    refreshed = Issue.objects.get()
    assert refreshed.pk == kept.pk
    assert (refreshed.title, refreshed.labels) == ("Renamed", ["bug"])
    assert refreshed.contribution_type == "bug_fix"


def test_issues_disabled_means_none(client, respx_mock) -> None:
    repo = fresh_repo()
    Issue.objects.create(
        repository=repo, github_id=1, number=1, title="old", html_url="https://github.com/x"
    )
    respx_mock.get(ISSUES).respond(410, json={"message": "Issues are disabled"})
    assert analyze(client, repo, ["issues"]) == Outcome.ANALYZED
    assert not Issue.objects.exists()


def test_failed_fetch_keeps_issues_and_restores_state(client, respx_mock) -> None:
    stamp = timezone.now() - timedelta(hours=7)
    repo = fresh_repo()
    respx_mock.get(ISSUES).respond(200, json=[issue_payload(1)])
    analyze(client, repo, ["issues"])
    Repository.objects.filter(pk=repo.pk).update(lifecycle="stale", issues_synced_at=stamp)

    respx_mock.get(ISSUES).respond(502)
    with pytest.raises(GitHubTransientError):
        analyze(client, repo, ["issues"])

    repo.refresh_from_db()
    assert Issue.objects.filter(repository=repo).count() == 1  # never treated as "no issues"
    assert repo.lifecycle == "stale"
    assert repo.issues_synced_at == stamp


def test_forbidden_fetch_recorded_as_failure(client, respx_mock) -> None:
    repo = fresh_repo()
    Issue.objects.create(
        repository=repo, github_id=1, number=1, title="kept", html_url="https://github.com/x"
    )
    respx_mock.get(ISSUES).respond(403, json={"message": "Forbidden"})
    assert analyze(client, repo, ["issues"]) == Outcome.FAILED
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.lifecycle_error) == ("failed", "forbidden")
    assert Issue.objects.filter(repository=repo).count() == 1


def test_issues_task_fetches_issues_only(respx_mock) -> None:
    repo = fresh_repo(lifecycle="stale", stale_parts=["issues"])
    expire_parts(repo, ["issues"])
    routes = mock_repo_api(respx_mock, "encode/httpx", 7, issues=[issue_payload(1)])

    tasks.sync_repository_issues.delay(repo.pk)

    assert routes["issues"].called
    called = [name for name, route in routes.items() if route.called]
    assert called == ["issues"]
    assert Repository.objects.get(pk=repo.pk).lifecycle == "recommendable"
    assert Issue.objects.count() == 1


def test_stale_sweep_and_backlog_for_issues_only(profile, monkeypatch) -> None:
    repo = fresh_repo(issues_synced_at=timezone.now() - timedelta(hours=7))
    add_candidate(profile, repo)

    assert tasks.mark_stale_repositories() == 1
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.stale_parts) == ("stale", ["issues"])

    queued: list[tuple[str, int]] = []
    monkeypatch.setattr(tasks.sync_repository, "delay", lambda pk: queued.append(("all", pk)))
    monkeypatch.setattr(
        tasks.sync_repository_issues, "delay", lambda pk: queued.append(("issues", pk))
    )
    tasks.process_repository_backlog()
    assert queued == [("issues", repo.pk)]


def test_analyzed_repository_without_issues_is_stale() -> None:
    repo = fresh_repo(issues_synced_at=None)
    assert stale_parts(repo, timezone.now()) == ["issues"]


def test_issues_shared_across_developers(client, respx_mock, profile) -> None:
    other = DeveloperProfile.objects.create(
        user=cast(User, UserFactory()), analyzed_at=timezone.now()
    )
    repo = make_candidate_repo(7, "encode/httpx")
    add_candidate(profile, repo)
    add_candidate(other, repo)
    routes = mock_repo_api(respx_mock, "encode/httpx", 7, issues=[issue_payload(1)])

    analyze(client, repo)
    analyze(client, repo)  # the second developer's discovery: everything is fresh

    assert routes["issues"].call_count == 1
    assert Issue.objects.count() == 1


# --- settings checks ------------------------------------------------------------------


def test_default_issue_config_is_valid() -> None:
    assert issue_config_check() == []
    assert settings.REPO_STALE_AFTER["issues"] == 6
    assert discovery_config_check() == []


@pytest.mark.parametrize("name", ["ISSUES_MAX_PAGES", "ISSUE_BODY_MAX_CHARS", "ISSUE_MAX_AGE_DAYS"])
@pytest.mark.parametrize("value", [0, -1, "1"])
def test_issue_limits_must_be_positive(name: str, value: object) -> None:
    with override_settings(**{name: value}):
        assert "core.E020" in ids(issue_config_check())


@pytest.mark.parametrize(
    "thresholds",
    [
        {"short_body": 600, "long_body": 4000, "many_technologies": 3},
        {**settings.ISSUE_DIFFICULTY, "extra": 1},
        {**settings.ISSUE_DIFFICULTY, "short_body": 5000},
        {**settings.ISSUE_DIFFICULTY, "many_technologies": 1},
        {**settings.ISSUE_DIFFICULTY, "long_discussion": 0},
        {**settings.ISSUE_DIFFICULTY, "several_technologies": 1},
        {**settings.ISSUE_DIFFICULTY, "several_technologies": 4},
        {**settings.ISSUE_DIFFICULTY, "min_votes": 1},
        {**settings.ISSUE_DIFFICULTY, "min_votes": 5},
    ],
    ids=[
        "missing",
        "unknown",
        "short-above-long",
        "few-technologies",
        "no-discussion",
        "several-below-two",
        "several-above-many",
        "one-vote",
        "unreachable-votes",
    ],
)
def test_difficulty_thresholds_checked(thresholds) -> None:
    with override_settings(ISSUE_DIFFICULTY=thresholds):
        assert "core.E040" in ids(issue_config_check())


def test_partial_difficulty_override_is_valid() -> None:
    # base.py spreads the ISSUE_DIFFICULTY JSON over the defaults, so one key is enough.
    with override_settings(ISSUE_DIFFICULTY={**settings.ISSUE_DIFFICULTY, "long_discussion": 20}):
        assert issue_config_check() == []


@pytest.mark.parametrize("min_votes", [3, 4])
def test_min_votes_above_intermediate_capacity_warns(min_votes: int) -> None:
    # Intermediate has two voters (labels, technology count): it could never win.
    with override_settings(ISSUE_DIFFICULTY={**settings.ISSUE_DIFFICULTY, "min_votes": min_votes}):
        found = issue_config_check()
    assert ids(found) == ["core.W004"]
    assert "intermediate" in found[0].msg and "beginner" not in found[0].msg


def test_issue_staleness_age_required() -> None:
    ages = {k: v for k, v in settings.REPO_STALE_AFTER.items() if k != "issues"}
    with override_settings(REPO_STALE_AFTER=ages):
        assert "core.E023" in ids(discovery_config_check())


@pytest.mark.parametrize(
    "labels",
    [
        "good first issue",
        ["good first issue", ""],
        ["help wanted", "Help Wanted"],
        [3],
        ["good first issue", " help wanted"],
        ["good first issue, help wanted"],
    ],
)
def test_entry_labels_checked(labels: object) -> None:
    with override_settings(ISSUES_ENTRY_LABELS=labels):
        assert "core.E041" in ids(issue_config_check())


@pytest.mark.parametrize("labels", [[], ["good first issue"], ["good first issue", "help wanted"]])
def test_entry_labels_valid(labels: list[str]) -> None:
    with override_settings(ISSUES_ENTRY_LABELS=labels):
        assert issue_config_check() == []


# --- entry labels (labeled-issue-fetch) ----------------------------------------------------


def capped_recent(respx_mock, issues: list[dict[str, Any]]):
    return respx_mock.get(ISSUES).respond(
        200, json=issues, headers={"Link": f'<{ISSUES}?page=2>; rel="next"'}
    )


def gfi(number: int, *names: str) -> dict[str, Any]:
    return issue_payload(number, labels=[{"name": n} for n in names or ("good first issue",)])


def test_capped_listing_adds_older_entry_issues_once(client, respx_mock) -> None:
    repo = fresh_repo()
    first = respx_mock.get(ISSUES, params={"labels": "good first issue"}).respond(
        200, json=[gfi(2), gfi(50, "good first issue", "help wanted")]
    )
    help_wanted = respx_mock.get(ISSUES, params={"labels": "help wanted"}).respond(
        200, json=[gfi(50, "good first issue", "help wanted"), gfi(60, "help wanted")]
    )
    capped_recent(respx_mock, [issue_payload(1), gfi(2)])

    analyze(client, repo, ["issues"])

    numbers = sorted(Issue.objects.filter(repository=repo).values_list("number", flat=True))
    assert numbers == [1, 2, 50, 60]  # #2 and #50 came twice, stored once
    assert first.call_count == help_wanted.call_count == 1
    repo.refresh_from_db()
    assert repo.issues_truncated is True  # the recent listing's cap, unchanged by labels


def test_untruncated_listing_fetches_no_labels(client, respx_mock) -> None:
    repo = fresh_repo()
    entry = respx_mock.get(ISSUES, params={"labels": "good first issue"}).respond(200, json=[])
    respx_mock.get(ISSUES).respond(200, json=[issue_payload(1), gfi(2)])
    analyze(client, repo, ["issues"])
    assert entry.call_count == 0
    assert Issue.objects.filter(repository=repo).count() == 2


@override_settings(ISSUES_ENTRY_LABELS=[])
def test_no_entry_labels_configured(client, respx_mock) -> None:
    repo = fresh_repo()
    recent = capped_recent(respx_mock, [issue_payload(1)])
    analyze(client, repo, ["issues"])
    assert len(respx_mock.calls) == recent.call_count == 1


def test_failed_labeled_listing_keeps_the_stored_issues(client, respx_mock) -> None:
    stamp = timezone.now() - timedelta(hours=7)
    repo = fresh_repo()
    # Labeled routes first: respx matches in registration order.
    respx_mock.get(ISSUES, params={"labels": "good first issue"}).respond(200, json=[gfi(9)])
    respx_mock.get(ISSUES, params={"labels": "help wanted"}).respond(502)
    respx_mock.get(ISSUES).side_effect = [
        httpx.Response(200, json=[issue_payload(1)]),  # first analysis: not capped
        httpx.Response(
            200, json=[issue_payload(2)], headers={"Link": f'<{ISSUES}?page=2>; rel="next"'}
        ),
    ]
    analyze(client, repo, ["issues"])
    Repository.objects.filter(pk=repo.pk).update(lifecycle="stale", issues_synced_at=stamp)

    with pytest.raises(GitHubTransientError):
        analyze(client, repo, ["issues"])

    repo.refresh_from_db()
    assert list(Issue.objects.filter(repository=repo).values_list("number", flat=True)) == [1]
    assert (repo.lifecycle, repo.issues_synced_at) == ("stale", stamp)


def test_merge_keeps_recent_order_and_truncation() -> None:
    def page(*numbers: int, truncated: bool = False) -> IssuePage:
        return IssuePage([IssueData.from_api(issue_payload(n)) for n in numbers], truncated)

    merged = merge_issue_pages(page(3, 1, truncated=True), [page(1, 7), page(7, 5)])
    assert [i.number for i in merged.issues] == [3, 1, 7, 5]
    assert merged.truncated is True
    assert [i.number for i in merge_issue_pages(page(2), []).issues] == [2]


def test_list_settings_are_trimmed(monkeypatch) -> None:
    from config.settings.base import env_list

    monkeypatch.setenv("CF_TEST_LIST", "good first issue, help wanted,,")
    assert env_list("CF_TEST_LIST", default=[]) == ["good first issue", "help wanted"]


def test_labeled_listings_renew_the_claim(client, respx_mock, monkeypatch) -> None:
    from services.repositories.analysis import RepositoryAnalysisService

    repo = fresh_repo()
    respx_mock.get(ISSUES, params={"labels": "good first issue"}).respond(200, json=[])
    respx_mock.get(ISSUES, params={"labels": "help wanted"}).respond(200, json=[])
    capped_recent(respx_mock, [issue_payload(1)])
    calls: list[int] = []
    original = RepositoryAnalysisService._between_parts

    def counting(self, r):
        calls.append(len(respx_mock.calls))
        return original(self, r)

    monkeypatch.setattr(RepositoryAnalysisService, "_between_parts", counting)
    analyze(client, repo, ["issues"])
    assert calls == [0, 1, 2]  # before the recent listing and before each labeled one
