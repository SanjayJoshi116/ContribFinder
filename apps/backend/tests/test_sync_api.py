from datetime import timedelta
from typing import cast
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
import respx
from django.conf import settings
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from github.models import GitHubAccount, GitHubProfile
from jobs.models import SyncJob
from repositories.models import Repository, RepositoryLanguage, RepositoryTopic, UserRepository
from services import data_deletion

from .factories import GitHubAccountFactory

pytestmark = pytest.mark.django_db

SYNC = SyncJob.JobType.GITHUB_PROFILE_SYNC
DELAY = "github.tasks.sync_github_profile.delay"


def make_job(user, status: str, **fields) -> SyncJob:
    return SyncJob.objects.create(user=user, job_type=SYNC, status=status, **fields)


# --- POST /profile/sync ---------------------------------------------------------------


def test_start_creates_pending_job_and_enqueues(
    signed_in_client: APIClient, user, django_capture_on_commit_callbacks
) -> None:
    with patch(DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
        response = signed_in_client.post("/api/v1/profile/sync")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "PENDING"
    assert list(body["steps"]) == [
        "profile",
        "readme",
        "repositories",
        "languages",
        "topics",
        "dependencies",
        "contributions",
        "analysis",
    ]
    assert "metadata" not in body and "error_detail" not in body
    delay.assert_called_once_with(body["id"])


def test_start_while_active_returns_same_job(signed_in_client: APIClient, user) -> None:
    running = make_job(user, "RUNNING")
    with patch(DELAY) as delay:
        response = signed_in_client.post("/api/v1/profile/sync")
    assert response.status_code == 202
    assert response.json()["id"] == running.pk
    assert SyncJob.objects.filter(user=user).count() == 1
    delay.assert_not_called()


def test_cooldown_rejects_with_retry_after(signed_in_client: APIClient, user) -> None:
    make_job(user, "COMPLETED", completed_at=timezone.now() - timedelta(minutes=1))
    response = signed_in_client.post("/api/v1/profile/sync")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "sync_cooldown"
    assert 230 <= int(response.headers["Retry-After"]) <= 240


def test_after_cooldown_a_new_sync_starts(signed_in_client: APIClient, user) -> None:
    make_job(user, "COMPLETED", completed_at=timezone.now() - timedelta(minutes=10))
    with patch(DELAY):
        assert signed_in_client.post("/api/v1/profile/sync").status_code == 202


def test_stale_running_job_does_not_block(signed_in_client: APIClient, user) -> None:
    stale = make_job(user, "RUNNING")
    SyncJob.objects.filter(pk=stale.pk).update(updated_at=timezone.now() - timedelta(hours=2))
    with patch(DELAY):
        response = signed_in_client.post("/api/v1/profile/sync")
    assert response.status_code == 202
    assert response.json()["id"] != stale.pk
    stale.refresh_from_db()
    assert (stale.status, stale.error_code) == ("FAILED", "worker_lost")


def test_start_without_github_account_is_409(signed_in_client: APIClient, user) -> None:
    GitHubAccount.objects.filter(user=user).delete()
    response = signed_in_client.post("/api/v1/profile/sync")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "github_not_connected"


def test_start_requires_csrf(csrf_client: APIClient, user) -> None:
    csrf_client.force_login(user)
    assert csrf_client.post("/api/v1/profile/sync").status_code == 403


# --- GET /sync/status -------------------------------------------------------------------


def test_status_never_synced(signed_in_client: APIClient) -> None:
    assert signed_in_client.get("/api/v1/sync/status").json() == {
        "job": None,
        "last_synced_at": None,
    }


def test_status_running_with_last_success(signed_in_client: APIClient, user) -> None:
    done_at = timezone.now() - timedelta(days=1)
    make_job(user, "COMPLETED", completed_at=done_at)
    running = make_job(user, "RUNNING", steps={"profile": "done", "readme": "running"})
    body = signed_in_client.get("/api/v1/sync/status").json()
    assert body["job"]["id"] == running.pk
    assert body["job"]["status"] == "RUNNING"
    # Steps missing from older jobs are reported as pending, in step order.
    assert body["job"]["steps"] == {
        "profile": "done",
        "readme": "running",
        **dict.fromkeys(
            ["repositories", "languages", "topics", "dependencies", "contributions", "analysis"],
            "pending",
        ),
    }
    assert body["last_synced_at"] is not None


def test_status_only_shows_own_jobs(signed_in_client: APIClient) -> None:
    other = GitHubAccountFactory().user
    make_job(other, "RUNNING")
    assert signed_in_client.get("/api/v1/sync/status").json()["job"] is None


def test_status_requires_auth(api_client: APIClient) -> None:
    assert api_client.get("/api/v1/sync/status").status_code == 401


# --- data endpoints -----------------------------------------------------------------------


@pytest.fixture
def synced(user):
    GitHubProfile.objects.create(
        user=user,
        github_id=1,
        login="octocat",
        name="The Octocat",
        bio="Builds tools",
        public_repos=2,
        has_profile_readme=True,
        profile_readme="## Skills",
        synced_at=timezone.now(),
    )
    now = timezone.now()
    for n, pushed in ((1, now - timedelta(days=5)), (2, now - timedelta(days=1))):
        repo = Repository.objects.create(
            github_id=n,
            owner_login="octocat",
            name=f"r{n}",
            full_name=f"octocat/r{n}",
            html_url=f"https://github.com/octocat/r{n}",
            pushed_at=pushed,
            synced_at=now,
        )
        UserRepository.objects.create(user=user, repository=repo)
        RepositoryLanguage.objects.create(repository=repo, language="Python", bytes=100 * n)
        RepositoryTopic.objects.create(repository=repo, topic="django")
    # Someone else's repository must not appear.
    other_repo = Repository.objects.create(
        github_id=99,
        owner_login="x",
        name="x",
        full_name="x/x",
        html_url="https://x",
        synced_at=now,
    )
    other_user = cast(GitHubAccount, GitHubAccountFactory()).user
    UserRepository.objects.create(user=other_user, repository=other_repo)


@respx.mock
def test_profile_github(signed_in_client: APIClient, synced) -> None:
    body = signed_in_client.get("/api/v1/profile/github").json()
    assert body["login"] == "octocat"
    assert body["has_profile_readme"] is True
    assert "profile_readme" not in body
    assert len(respx.mock.calls) == 0  # served from the database only


def test_profile_github_not_synced(signed_in_client: APIClient) -> None:
    response = signed_in_client.get("/api/v1/profile/github")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_synced"


@respx.mock
def test_repositories_list(signed_in_client: APIClient, synced) -> None:
    body = signed_in_client.get("/api/v1/profile/repositories").json()
    assert body["count"] == 2
    assert [r["name"] for r in body["results"]] == ["r2", "r1"]  # most recently pushed first
    assert body["results"][0]["languages"] == [{"language": "Python", "bytes": 200}]
    assert body["results"][0]["topics"] == ["django"]
    assert len(respx.mock.calls) == 0


# --- triggers -----------------------------------------------------------------------------

TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"
IDENTITY = {"id": 5150, "login": "newbie", "name": "New", "avatar_url": "https://a/1"}


def sign_in(client: Client, router: respx.MockRouter) -> None:
    router.post(TOKEN_URL).respond(200, json={"access_token": "gho_x" * 8, "scope": ""})
    router.get(USER_URL).respond(200, json=IDENTITY)
    response = client.get("/api/v1/auth/github")
    state = parse_qs(urlparse(response["Location"]).query)["state"][0]
    client.get("/api/v1/auth/github/callback", {"code": "c", "state": state})


@respx.mock
def test_first_sign_in_enqueues_sync(client: Client, django_capture_on_commit_callbacks) -> None:
    with patch(DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
        sign_in(client, respx.mock)
    job = SyncJob.objects.get(user__github_account__github_id=5150)
    assert job.status == "PENDING"
    delay.assert_called_once_with(job.pk)


@respx.mock
def test_returning_synced_user_does_not_enqueue(client: Client) -> None:
    with patch(DELAY):
        sign_in(client, respx.mock)
    SyncJob.objects.update(status="COMPLETED", completed_at=timezone.now())
    client.logout()
    with patch(DELAY) as delay:
        sign_in(client, respx.mock)
    delay.assert_not_called()
    assert SyncJob.objects.count() == 1


@respx.mock
def test_sign_in_succeeds_even_if_enqueue_fails(client: Client) -> None:
    with patch("services.jobs.start_profile_sync", side_effect=RuntimeError("broker down")):
        sign_in(client, respx.mock)
    assert client.get("/api/v1/auth/me").status_code == 200


@respx.mock
@pytest.mark.parametrize("status", ["PENDING", "RUNNING", "RETRYING"])
def test_disconnect_cancels_active_sync(
    signed_in_client: APIClient, user, status: str, monkeypatch
) -> None:
    respx.mock.delete(
        f"https://api.github.com/applications/{settings.GITHUB_CLIENT_ID}/grant"
    ).respond(204)
    job = make_job(user, status)
    seen: list[str] = []
    real_delete = data_deletion.delete_github_data

    def spy(u):
        seen.append(SyncJob.objects.get(pk=job.pk).status)  # cancelled before any deletion
        return real_delete(u)

    monkeypatch.setattr(data_deletion, "delete_github_data", spy)
    signed_in_client.post("/api/v1/auth/github/disconnect")
    assert seen == ["CANCELLED"]
    assert not SyncJob.objects.filter(pk=job.pk).exists()  # job history is GitHub data


def test_repositories_page_size_param(signed_in_client: APIClient, synced) -> None:
    body = signed_in_client.get("/api/v1/profile/repositories?page_size=1").json()
    assert body["count"] == 2
    assert len(body["results"]) == 1
    capped = signed_in_client.get("/api/v1/profile/repositories?page_size=1000").json()
    assert len(capped["results"]) == 2  # max_page_size caps the request, never errors
