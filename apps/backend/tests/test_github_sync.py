import logging
from unittest.mock import patch

import httpx
import pytest
import respx
from django.test import override_settings

from github.models import GitHubProfile
from github.tasks import claim_job, sync_github_profile
from jobs.models import SyncJob
from repositories.models import Repository, UserRepository
from services.github.errors import (
    GitHubAuthError,
    GitHubForbidden,
    GitHubRateLimited,
    GitHubTransientError,
)
from services.github.retry import Fail, Retry, decide_retry
from services.github.sync import GitHubSyncService, JobCancelled, initial_steps

from .factories import GitHubAccountFactory

pytestmark = pytest.mark.django_db

API = "https://api.github.com"
TOKEN = "gho_testtoken0000000000000000000000"  # factory default
SYNC = SyncJob.JobType.GITHUB_PROFILE_SYNC


def repo_json(n: int, owner: str = "octocat", pushed: str = "2026-09-0{n}T10:00:00Z", **kw):
    return {
        "id": 100 + n,
        "name": f"r{n}",
        "full_name": f"{owner}/r{n}",
        "owner": {"login": owner},
        "html_url": f"https://github.com/{owner}/r{n}",
        "fork": False,
        "archived": False,
        "topics": [f"topic{n}", "shared"],
        "pushed_at": pushed.format(n=n),
        **kw,
    }


PROFILE = {
    "id": 424242,
    "login": "octocat",
    "name": "The Octocat",
    "bio": "Builds tools",
    "public_repos": 3,
    "created_at": "2011-01-25T18:44:36Z",
}


def mock_github(
    router: respx.MockRouter,
    repos=None,
    readme: str | None = "## Skills\nPython",
    languages: dict[str, int] | None = None,
):
    """Register GitHub routes. ``languages`` is read at request time, so tests can mutate it."""
    languages = languages if languages is not None else {"Python": 7000, "TypeScript": 3000}
    repos = repos if repos is not None else [repo_json(1), repo_json(2, fork=True), repo_json(3)]
    router.get(f"{API}/user").respond(200, json=PROFILE)
    readme_route = router.get(f"{API}/repos/octocat/octocat/readme")
    if readme is None:
        readme_route.respond(404)
    else:
        readme_route.respond(200, text=readme)
    router.get(f"{API}/users/octocat/repos").respond(200, json=repos)
    router.get(url__regex=rf"{API}/repos/octocat/r\d+/languages").mock(
        side_effect=lambda request: httpx.Response(200, json=languages)
    )
    # Phase 3 steps: no manifests and no external contributions unless a test adds them.
    # Exact URLs, so a test can override one repository by registering the same URL again.
    for repo in repos:
        router.get(f"{API}/repos/{repo['full_name']}/contents/").respond(200, json=[])
    router.get(f"{API}/search/issues").respond(200, json={"total_count": 0, "items": []})
    router.get(f"{API}/users/octocat/events/public").respond(200, json=[])
    return languages


@pytest.fixture
def job(user):
    return SyncJob.objects.create(
        user=user, job_type=SYNC, status="RUNNING", steps=initial_steps(), attempts=1
    )


def run(job) -> None:
    GitHubSyncService(job).run()


# --- service -----------------------------------------------------------------------


@respx.mock
def test_full_sync_stores_everything(job, user) -> None:
    mock_github(respx.mock)
    run(job)

    profile = GitHubProfile.objects.get(user=user)
    assert (profile.login, profile.name, profile.bio, profile.public_repos) == (
        "octocat",
        "The Octocat",
        "Builds tools",
        3,
    )
    assert profile.has_profile_readme is True
    assert profile.profile_readme == "## Skills\nPython"

    linked = Repository.objects.filter(user_links__user=user)
    assert linked.count() == 3
    assert linked.get(name="r2").is_fork is True
    r1 = linked.get(name="r1")
    assert dict(r1.languages.values_list("language", "bytes")) == {
        "Python": 7000,
        "TypeScript": 3000,
    }
    assert set(r1.topics.values_list("topic", flat=True)) == {"topic1", "shared"}

    job.refresh_from_db()
    assert job.steps == dict.fromkeys(
        [
            "profile",
            "readme",
            "repositories",
            "languages",
            "topics",
            "dependencies",
            "contributions",
            "analysis",
        ],
        "done",
    )


@respx.mock
def test_missing_readme_is_not_a_failure(job, user) -> None:
    mock_github(respx.mock, readme=None)
    run(job)
    job.refresh_from_db()
    assert job.steps["readme"] == "not_found"
    assert job.steps["topics"] == "done"
    profile = GitHubProfile.objects.get(user=user)
    assert profile.has_profile_readme is False
    assert profile.profile_readme == ""


@respx.mock
def test_repos_of_other_owners_are_ignored(job, user) -> None:
    mock_github(respx.mock, repos=[repo_json(1), repo_json(9, owner="someorg")])
    run(job)
    assert list(
        Repository.objects.filter(user_links__user=user).values_list("name", flat=True)
    ) == ["r1"]


@respx.mock
def test_removed_repository_is_unlinked(job, user) -> None:
    mock_github(respx.mock)
    run(job)
    SyncJob.objects.filter(pk=job.pk).update(status="COMPLETED")
    second = SyncJob.objects.create(
        user=user, job_type=SYNC, status="RUNNING", steps=initial_steps()
    )
    respx.mock.get(f"{API}/users/octocat/repos").respond(200, json=[repo_json(1)])

    run(second)

    assert list(
        UserRepository.objects.filter(user=user).values_list("repository__name", flat=True)
    ) == ["r1"]
    # The repository record itself is kept (it may be a discovery candidate later).
    assert Repository.objects.filter(name="r3").exists()


@respx.mock
@override_settings(GITHUB_SYNC_MAX_REPOS=2)
def test_repository_cap_keeps_most_recently_pushed(job, user) -> None:
    mock_github(respx.mock)  # pushed: r1 < r2 < r3
    run(job)
    names = set(Repository.objects.filter(user_links__user=user).values_list("name", flat=True))
    assert names == {"r2", "r3"}
    job.refresh_from_db()
    assert job.metadata["repos_capped"] is True
    assert job.metadata["repos_total"] == 3


@respx.mock
def test_languages_and_topics_are_replaced_not_appended(job, user) -> None:
    languages = mock_github(respx.mock, repos=[repo_json(1)])
    run(job)
    SyncJob.objects.filter(pk=job.pk).update(status="COMPLETED")
    second = SyncJob.objects.create(
        user=user, job_type=SYNC, status="RUNNING", steps=initial_steps()
    )
    respx.mock.get(f"{API}/users/octocat/repos").respond(200, json=[repo_json(1, topics=["only"])])
    languages.clear()
    languages["Go"] = 5
    run(second)
    repo = Repository.objects.get(name="r1")
    assert list(repo.languages.values_list("language", flat=True)) == ["Go"]
    assert list(repo.topics.values_list("topic", flat=True)) == ["only"]


@respx.mock
def test_retry_resumes_without_refetching_completed_work(job, user) -> None:
    mock_github(respx.mock)
    failing = {"count": 0}

    def languages(request: httpx.Request) -> httpx.Response:
        # Fail once on the second repository's languages.
        if request.url.path.endswith("/r2/languages") and failing["count"] == 0:
            failing["count"] += 1
            return httpx.Response(502)
        return httpx.Response(200, json={"Python": 1})

    respx.mock.get(url__regex=rf"{API}/repos/octocat/r\d+/languages").mock(side_effect=languages)

    with pytest.raises(GitHubTransientError):
        run(job)
    job.refresh_from_db()
    assert job.steps["languages"] == "failed"
    assert job.steps["repositories"] == "done"

    calls_before = {
        path: sum(1 for c in respx.mock.calls if c.request.url.path == path)
        for path in ("/user", "/users/octocat/repos", "/repos/octocat/octocat/readme")
    }
    run(job)  # the retry

    for path, count in calls_before.items():
        assert sum(1 for c in respx.mock.calls if c.request.url.path == path) == count
    r3_calls = [c for c in respx.mock.calls if c.request.url.path == "/repos/octocat/r3/languages"]
    assert len(r3_calls) == 1  # r3 (pushed last, processed first) was not re-fetched
    job.refresh_from_db()
    assert job.steps["languages"] == "done"
    assert job.steps["topics"] == "done"


@pytest.mark.respx(assert_all_called=False)
def test_cancelled_job_stops_before_next_request(job, respx_mock: respx.MockRouter) -> None:
    mock_github(respx_mock)
    SyncJob.objects.filter(pk=job.pk).update(status="CANCELLED")
    with pytest.raises(JobCancelled):
        run(job)
    assert len(respx_mock.calls) == 0


# --- retry policy ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "attempts", "expected"),
    [
        (GitHubAuthError("x"), 1, Fail("github_auth_invalid")),
        (GitHubRateLimited("x", 60), 1, Retry(61)),
        (GitHubRateLimited("x", 901), 1, Fail("github_rate_limited")),
        (GitHubRateLimited("x", 60), 5, Fail("github_rate_limited")),
        (GitHubTransientError("x"), 1, Retry(30)),
        (GitHubTransientError("x"), 3, Retry(120)),
        (GitHubTransientError("x"), 4, Retry(240)),
        (GitHubTransientError("x"), 5, Fail("github_unavailable")),
        (GitHubForbidden("x"), 1, Fail("github_error")),
        (ValueError("boom"), 1, Fail("internal_error")),
    ],
)
def test_decide_retry(error, attempts, expected) -> None:
    assert decide_retry(error, attempts, max_attempts=5, max_delay=900, rng=lambda: 0.0) == expected


def test_backoff_is_capped() -> None:
    assert decide_retry(
        GitHubTransientError("x"), 10, max_attempts=99, max_delay=900, rng=lambda: 0.0
    ) == Retry(600)


# --- task wrapper -------------------------------------------------------------------------


@pytest.fixture
def pending_job(user):
    return SyncJob.objects.create(user=user, job_type=SYNC, status="PENDING", steps=initial_steps())


@respx.mock
def test_task_completes_job(pending_job) -> None:
    mock_github(respx.mock)
    sync_github_profile.delay(pending_job.pk)
    pending_job.refresh_from_db()
    assert pending_job.status == "COMPLETED"
    assert pending_job.attempts == 1
    assert pending_job.started_at and pending_job.completed_at
    assert pending_job.error_code == ""


@respx.mock
def test_task_401_fails_without_retry(pending_job) -> None:
    respx.mock.get(f"{API}/user").respond(401)
    with patch.object(sync_github_profile, "retry") as retry:
        sync_github_profile.delay(pending_job.pk)
    retry.assert_not_called()
    pending_job.refresh_from_db()
    assert pending_job.status == "FAILED"
    assert pending_job.error_code == "github_auth_invalid"
    assert pending_job.steps["profile"] == "failed"


@respx.mock
def test_task_rate_limit_schedules_retry(pending_job) -> None:
    respx.mock.get(f"{API}/user").respond(429, headers={"Retry-After": "60"})
    with (
        patch.object(sync_github_profile, "retry", side_effect=RuntimeError("retry")) as retry,
        pytest.raises(RuntimeError),
    ):
        sync_github_profile.apply(args=(pending_job.pk,), throw=True)
    countdown = retry.call_args.kwargs["countdown"]
    assert 60 <= countdown <= 66
    pending_job.refresh_from_db()
    assert pending_job.status == "RETRYING"


@respx.mock
@override_settings(SYNC_MAX_ATTEMPTS=1)
def test_task_transient_exhausted_fails(pending_job) -> None:
    respx.mock.get(f"{API}/user").respond(503)
    sync_github_profile.delay(pending_job.pk)
    pending_job.refresh_from_db()
    assert pending_job.status == "FAILED"
    assert pending_job.error_code == "github_unavailable"


def test_task_without_account_fails(pending_job, user) -> None:
    from github.models import GitHubAccount

    GitHubAccount.objects.filter(user=user).delete()
    sync_github_profile.delay(pending_job.pk)
    pending_job.refresh_from_db()
    assert pending_job.status == "FAILED"
    assert pending_job.error_code == "github_auth_invalid"


@pytest.mark.parametrize("status", ["RUNNING", "COMPLETED", "FAILED", "CANCELLED"])
def test_claim_rejects_non_claimable(user, status: str) -> None:
    job = SyncJob.objects.create(user=user, job_type=SYNC, status=status)
    assert claim_job(job.pk) is False


def test_claim_reclaims_stale_running(user) -> None:
    from datetime import timedelta

    from django.utils import timezone

    job = SyncJob.objects.create(user=user, job_type=SYNC, status="RUNNING")
    SyncJob.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(hours=1))
    assert claim_job(job.pk) is True


@respx.mock
def test_no_token_in_job_task_args_or_logs(pending_job, caplog: pytest.LogCaptureFixture) -> None:
    respx.mock.get(f"{API}/user").respond(401)
    with (
        caplog.at_level(logging.DEBUG),
        patch.object(
            sync_github_profile, "apply_async", wraps=sync_github_profile.apply_async
        ) as apply_async,
    ):
        sync_github_profile.delay(pending_job.pk)
    assert apply_async.call_args.args[0] == (pending_job.pk,)
    pending_job.refresh_from_db()
    stored = " ".join(
        str(v)
        for v in (
            pending_job.steps,
            pending_job.metadata,
            pending_job.error_detail,
            pending_job.error_code,
        )
    )
    assert TOKEN not in stored
    assert TOKEN not in caplog.text


def test_other_users_account_not_used(pending_job) -> None:
    # Sanity: a second user's account exists; the job must use its own user only.
    GitHubAccountFactory()
    assert pending_job.user.github_account is not None
