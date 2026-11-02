"""GitHub service fixes from the review sweep (Bug_Backlog.md batch 32, change
github-services-review-fixes)."""

import time
from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest
import respx
from celery.exceptions import Retry
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.models import User
from github.tasks import revoke_later
from jobs.models import SyncJob
from repositories.models import Repository, UserRepository
from services.crypto import encrypt_token
from services.github import oauth, storage
from services.github.errors import GitHubClientError, GitHubRateLimited, GitHubTransientError

from .test_github_auth import GRANT_URL, TOKEN
from .test_github_client import client  # noqa: F401  (fixture)
from .test_github_sync import API, job, mock_github, repo_json, run, running_sync_job  # noqa: F401
from .test_github_sync_profile import calls, mock_contributions, pr

pytestmark = pytest.mark.django_db

CONTRIBUTOR = UserRepository.Relation.CONTRIBUTOR


def finish(job: SyncJob) -> None:
    SyncJob.objects.filter(pk=job.pk).update(status="COMPLETED")


# --- GHS-1: GitHub ID order ------------------------------------------------------------------


@respx.mock
@override_settings(GITHUB_SYNC_MAX_REPOS=2)
def test_repositories_are_chosen_by_push_and_stored_by_github_id(job: SyncJob) -> None:
    # Pushed r1 < r2 < r3 (GitHub IDs 101 < 102 < 103): the cap keeps r3 and r2.
    mock_github(respx.mock, repos=[repo_json(3), repo_json(1), repo_json(2)])
    with patch("services.github.sync.upsert_repository", wraps=storage.upsert_repository) as up:
        run(job)
    assert [c.args[0].github_id for c in up.call_args_list] == [102, 103]


# --- GHS-2: row lock before the replace -------------------------------------------------------


@pytest.mark.parametrize("table", ["repositorylanguage", "repositorydependency"])
@respx.mock
def test_sync_locks_the_repository_row_before_each_replace(job: SyncJob, table: str) -> None:
    mock_github(respx.mock, repos=[repo_json(1)])
    respx.get(f"{API}/repos/octocat/r1/contents/").respond(
        200, json=[{"name": "requirements.txt", "type": "file", "size": 7}]
    )
    respx.get(f"{API}/repos/octocat/r1/contents/requirements.txt").respond(200, text="django\n")
    with CaptureQueriesContext(connection) as ctx:
        run(job)
    sqls = [q["sql"] for q in ctx.captured_queries]
    deletes = [i for i, s in enumerate(sqls) if s.startswith("DELETE") and table in s]
    assert deletes
    for delete in deletes:
        lock = max(
            i
            for i, s in enumerate(sqls[:delete])
            if "FOR UPDATE" in s and "repositories_repository" in s
        )
        # The row lock is the latest lock taken before the replace (inside the same write).
        assert not any("COMMIT" in s or "RELEASE SAVEPOINT" in s for s in sqls[lock:delete])


# --- GHS-3: next-page link origin -------------------------------------------------------------


@pytest.mark.parametrize(
    "link",
    [
        f"{API.replace('https://', 'http://')}/users/octocat/repos?page=2",
        "https://api.github.com:8443/users/octocat/repos?page=2",
    ],
)
@respx.mock
def test_next_link_outside_the_api_origin_is_refused(client, link: str) -> None:
    respx.get(f"{API}/users/octocat/repos").respond(
        200, json=[repo_json(1)], headers={"Link": f'<{link}>; rel="next"'}
    )
    with pytest.raises(GitHubClientError):
        client.list_owned_repositories("octocat")
    assert len(respx.calls) == 1  # never followed: the token stays on the API origin


# --- GHS-4: rate-limited revocation is retried ------------------------------------------------


RATE_LIMITS = [
    httpx.Response(403, headers={"X-RateLimit-Remaining": "0"}),
    httpx.Response(403, json={"message": "You have exceeded a secondary rate limit."}),
]


@pytest.mark.parametrize("answer", RATE_LIMITS)
@respx.mock
def test_rate_limited_revocation_raises_rate_limited(answer: httpx.Response) -> None:
    respx.delete(GRANT_URL).mock(return_value=answer)
    with pytest.raises(GitHubRateLimited):
        oauth.revoke_grant(TOKEN)


@pytest.mark.parametrize("answer", RATE_LIMITS)
@respx.mock
@override_settings(CELERY_TASK_ALWAYS_EAGER=False)  # with a worker
def test_rate_limited_revocation_is_retried(answer: httpx.Response) -> None:
    respx.delete(GRANT_URL).mock(return_value=answer)
    with pytest.raises(Retry):
        revoke_later.apply(args=(encrypt_token(TOKEN), None, True), throw=True)


@respx.mock
@override_settings(CELERY_TASK_ALWAYS_EAGER=False, GITHUB_MAX_RETRY_DELAY=900)
def test_long_rate_limited_revocation_is_retried_after_the_cap() -> None:
    reset = str(int(time.time()) + 3600)  # an hour away, above the cap
    respx.delete(GRANT_URL).respond(
        403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": reset}
    )
    with (
        patch.object(revoke_later, "retry", side_effect=Retry()) as retry,
        pytest.raises(Retry),
    ):
        revoke_later.apply(args=(encrypt_token(TOKEN), None, True), throw=True)
    countdown = retry.call_args.kwargs["countdown"]
    assert 900 < countdown <= 900 + 6  # the cap, plus the policy's 1 s and jitter


@respx.mock
def test_other_forbidden_revocation_is_final() -> None:
    respx.delete(GRANT_URL).respond(403, json={"message": "Forbidden"})
    with pytest.raises(oauth.OAuthError) as raised:
        oauth.revoke_grant(TOKEN)
    assert raised.value.code == "revocation_failed"


# --- GHS-7: httpx errors become GitHub errors -------------------------------------------------


@respx.mock
def test_decoding_error_is_transient(client) -> None:
    respx.get(f"{API}/repos/o/r/languages").mock(side_effect=httpx.DecodingError)
    with pytest.raises(GitHubTransientError):
        client.get_languages("o/r")


@respx.mock
def test_malformed_next_link_is_a_client_error(client) -> None:
    # httpx itself reports a malformed Location as a protocol error (transient); a Link URL
    # is parsed here.
    respx.get(f"{API}/users/octocat/repos").respond(
        200, json=[repo_json(1)], headers={"Link": '<https://[::1/x>; rel="next"'}
    )
    with pytest.raises(GitHubClientError):
        client.list_owned_repositories("octocat")


# --- GHS-8: cache size cap --------------------------------------------------------------------


@respx.mock
@override_settings(GITHUB_ETAG_MAX_BYTES=20)
def test_body_above_the_cap_is_not_cached(client) -> None:
    route = respx.get(f"{API}/repos/o/r/languages")
    route.respond(200, json={"Python": 1234567890, "Go": 1}, headers={"ETag": '"big"'})
    assert client.get_languages("o/r") == {"Python": 1234567890, "Go": 1}
    client.get_languages("o/r")
    assert "If-None-Match" not in route.calls[1].request.headers


@respx.mock
@override_settings(GITHUB_ETAG_MAX_BYTES=20)
def test_body_within_the_cap_is_cached(client) -> None:
    route = respx.get(f"{API}/repos/o/r/languages")
    route.side_effect = [
        httpx.Response(200, json={"Go": 1}, headers={"ETag": '"small"'}),
        httpx.Response(304),
    ]
    client.get_languages("o/r")
    assert client.get_languages("o/r") == {"Go": 1}
    assert route.calls[1].request.headers["If-None-Match"] == '"small"'


# --- GHS-5, GHS-6: contributions ---------------------------------------------------------------


@respx.mock
def test_contributions_under_an_old_and_a_new_name_add_up(job: SyncJob, user: User) -> None:
    mock_github(respx.mock, repos=[repo_json(1)])
    mock_contributions(respx.mock, prs=["old-org/proj"] * 3, pushes=("new-org/proj",) * 2)
    current = repo_json(
        77, owner="new-org", full_name="new-org/proj", pushed="2026-08-01T10:00:00Z"
    )
    respx.get(f"{API}/repos/old-org/proj").respond(
        301, headers={"Location": f"{API}/repositories/177"}
    )
    respx.get(f"{API}/repositories/177").respond(200, json=current)
    respx.get(f"{API}/repos/new-org/proj").respond(200, json=current)

    run(job)

    [link] = UserRepository.objects.filter(user=user, relation=CONTRIBUTOR)
    assert link.repository.full_name == "new-org/proj"
    assert (link.merged_pr_count, link.push_count) == (3, 2)
    assert link.last_contributed_at is not None


def _sync_then_answer(user: User, job: SyncJob, status: int) -> SyncJob:
    """A first sync links ``pallets/flask`` (3 PRs); a second one sees it answer ``status``."""
    mock_github(respx.mock, repos=[repo_json(1)])
    mock_contributions(respx.mock, prs=["pallets/flask"] * 3)
    run(job)
    finish(job)
    respx.get(f"{API}/search/issues").respond(200, json={"items": [pr("pallets/flask")]})
    respx.get(f"{API}/repos/pallets/flask").respond(status, json={"message": "Forbidden"})
    second = running_sync_job(user)
    run(second)
    second.refresh_from_db()
    assert second.steps["contributions"] == "done"
    return second


@respx.mock
def test_unreadable_contributed_repository_keeps_its_link(job: SyncJob, user: User) -> None:
    second = _sync_then_answer(user, job, 403)
    [link] = UserRepository.objects.filter(user=user, relation=CONTRIBUTOR)
    assert link.repository.full_name == "pallets/flask"
    assert link.merged_pr_count == 3  # the previous counts, not this run's
    assert second.metadata["contrib_skipped"] == ["pallets/flask"]


@respx.mock
def test_gone_contributed_repository_drops_its_link(job: SyncJob, user: User) -> None:
    second = _sync_then_answer(user, job, 404)
    assert not UserRepository.objects.filter(user=user, relation=CONTRIBUTOR).exists()
    assert second.metadata["contrib_skipped"] == []


# --- GHS-9: frozen dependencies set -----------------------------------------------------------


@respx.mock
@override_settings(GITHUB_MANIFEST_MAX_REPOS=1)
def test_retried_dependencies_step_reads_the_first_set(job: SyncJob) -> None:
    mock_github(respx.mock, repos=[repo_json(1), repo_json(2)])  # r2 pushed later: chosen
    respx.get(f"{API}/repos/octocat/r2/contents/").mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json=[])]
    )
    with pytest.raises(GitHubTransientError):
        run(job)
    # Pushed since: a fresh choice would now read r1.
    Repository.objects.filter(full_name="octocat/r1").update(
        pushed_at=timezone.now() + timedelta(days=1)
    )
    run(job)
    assert calls("/repos/octocat/r2/contents/") == 2
    assert calls("/repos/octocat/r1/contents/") == 0
    job.refresh_from_db()
    assert job.metadata["dependencies_ids"] == [Repository.objects.get(full_name="octocat/r2").pk]
