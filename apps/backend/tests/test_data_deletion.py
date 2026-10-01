"""Deleting GitHub-derived data, account deletion and disconnect (Phase 8a, group 4)."""

import logging
from typing import Any, cast

import httpx
import pytest
import respx
from django.conf import settings
from django.core.cache import cache
from django.core.cache.backends.redis import RedisCache
from django.test import Client
from django.utils import timezone

from accounts.models import AuditEvent, User
from developers.models import DeveloperProfile, DeveloperSkill, SkillEvidence
from feedback.models import DismissedRepository, RecommendationFeedback, SavedRepository
from github.models import GitHubAccount, GitHubProfile
from jobs.models import SyncJob
from recommendations.models import Recommendation, RecommendationReason
from repositories.models import (
    CandidateDiscovery,
    Repository,
    RepositoryCandidate,
    RepositoryLanguage,
    UserRepository,
)
from services import data_deletion, feedback

from .factories import GitHubAccountFactory
from .repo_fixtures import add_candidate
from .test_github_auth import callback, mock_github_ok, start
from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    generate,
    pool,
)

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]

GRANT_URL = f"https://api.github.com/applications/{settings.GITHUB_CLIENT_ID}/grant"
FACTORY_TOKEN = "gho_testtoken0000000000000000000000"

PER_USER_MODELS = (
    GitHubProfile,
    UserRepository,
    DeveloperProfile,
    DeveloperSkill,
    SkillEvidence,
    RepositoryCandidate,
    CandidateDiscovery,
    Recommendation,
    RecommendationReason,
    SavedRepository,
    DismissedRepository,
    RecommendationFeedback,
    SyncJob,
)


@pytest.fixture
def everything(user, synced, developer, pool):  # noqa: F811
    """A user with a synced profile, recommendations, saves, dismissals, feedback and jobs."""
    generate(user)
    django_rec = Recommendation.objects.get(repository=pool["django"])
    plain_rec = Recommendation.objects.get(repository=pool["plain"])
    feedback.record(user, django_rec, "viewed")
    feedback.save(user, django_rec)
    feedback.dismiss(user, plain_rec)
    SyncJob.objects.create(user=user, job_type="github_profile_sync", status="COMPLETED")
    return pool


def csrf_client(user: User) -> tuple[Client, str]:
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    client.get("/api/v1/auth/csrf/")
    return client, client.cookies["csrftoken"].value


def assert_no_user_data() -> None:
    for model in PER_USER_MODELS:
        assert not model.objects.exists(), model.__name__


# --- The routine ----------------------------------------------------------------------


def test_delete_github_data_empties_every_per_user_table(user, everything) -> None:
    for model in PER_USER_MODELS:
        assert model.objects.exists(), model.__name__
    counts = data_deletion.delete_github_data(user)
    assert_no_user_data()
    assert User.objects.filter(pk=user.pk).exists()
    assert GitHubAccount.objects.filter(user=user).exists()
    assert counts["recommendations"] >= 1 and counts["saved"] == 1 and counts["dismissed"] == 1
    assert all(isinstance(value, int) for value in counts.values())


def test_shared_repository_kept_and_orphan_deleted(user, everything) -> None:
    other = cast(GitHubAccount, GitHubAccountFactory()).user
    other_profile = DeveloperProfile.objects.create(user=other, analyzed_at=timezone.now())
    add_candidate(other_profile, everything["django"])
    data_deletion.delete_github_data(user)
    kept = Repository.objects.get(pk=everything["django"].pk)
    assert RepositoryLanguage.objects.filter(repository=kept).exists()  # analysis kept
    assert RepositoryCandidate.objects.filter(developer=other_profile).count() == 1
    assert not Repository.objects.filter(pk=everything["plain"].pk).exists()
    assert not Repository.objects.filter(pk=everything["go"].pk).exists()
    assert not Repository.objects.filter(full_name__startswith="me/").exists()


def test_other_users_feedback_survives_shared_repository_deletion(user, everything) -> None:
    other = cast(GitHubAccount, GitHubAccountFactory()).user
    RecommendationFeedback.objects.create(
        user=other,
        repository=everything["go"],
        repository_full_name="other/goserver",
        action="viewed",
    )
    data_deletion.delete_github_data(user)
    event = RecommendationFeedback.objects.get(user=other)
    assert event.repository is None and event.repository_full_name == "other/goserver"


def test_cache_purge_removes_user_scope_only(user, django_capture_on_commit_callbacks) -> None:
    other_id = user.pk + 1000
    cache.set(f"github:etag:{user.pk}:abc", {"etag": "x"})
    cache.set(f"github:etag:{user.pk}:def", {"etag": "y"})
    cache.set(f"github:ratelimit:{user.pk}", {"remaining": 1})
    cache.set("github:etag:public:abc", {"etag": "z"})
    cache.set(f"github:etag:{other_id}:abc", {"etag": "w"})
    with django_capture_on_commit_callbacks(execute=True):
        data_deletion.delete_github_data(user)
    assert cache.get(f"github:etag:{user.pk}:abc") is None
    assert cache.get(f"github:etag:{user.pk}:def") is None
    assert cache.get(f"github:ratelimit:{user.pk}") is None
    assert cache.get("github:etag:public:abc") is not None
    assert cache.get(f"github:etag:{other_id}:abc") is not None


def test_cache_purge_on_redis_scans_the_user_prefix(monkeypatch) -> None:
    redis_cache = RedisCache("redis://localhost:6379/1", {})
    deleted: list[Any] = []

    class FakeClient:
        def scan_iter(self, match: str, count: int):
            assert match == redis_cache.make_key("github:etag:7:*")
            return iter([b":1:github:etag:7:a", b":1:github:etag:7:b"])

        def delete(self, *keys: Any) -> None:
            deleted.extend(keys)

    class FakePool:
        def get_client(self, write: bool) -> FakeClient:
            return FakeClient()

    monkeypatch.setattr(redis_cache, "delete", lambda key: deleted.append(key))
    redis_cache.__dict__["_cache"] = FakePool()
    monkeypatch.setattr(data_deletion, "caches", {"default": redis_cache})
    data_deletion.purge_user_github_cache(7)
    assert deleted == ["github:ratelimit:7", b":1:github:etag:7:a", b":1:github:etag:7:b"]


def test_cache_purge_failure_is_logged_not_raised(monkeypatch, caplog) -> None:
    class Broken:
        def delete(self, key: str) -> None:
            raise ConnectionError("down")

    monkeypatch.setattr(data_deletion, "caches", {"default": Broken()})
    with caplog.at_level(logging.WARNING):
        data_deletion.purge_user_github_cache(1)
    assert "cache purge failed" in caplog.text


def test_active_jobs_cancelled_before_deletion(user, synced, monkeypatch) -> None:
    job = SyncJob.objects.create(user=user, job_type="github_profile_sync", status="RUNNING")
    statuses: list[str] = []
    real = DeveloperProfile.objects.filter

    def spy(*args, **kwargs):
        statuses.append(SyncJob.objects.get(pk=job.pk).status)
        return real(*args, **kwargs)

    monkeypatch.setattr(DeveloperProfile.objects, "filter", spy)
    data_deletion.delete_github_data(user)
    assert statuses[0] == "CANCELLED"
    assert not SyncJob.objects.exists()


# --- DELETE /profile/github-data ------------------------------------------------------


def test_delete_github_data_endpoint(user, everything, caplog) -> None:
    client, csrf = csrf_client(user)
    with caplog.at_level(logging.DEBUG):
        response = client.delete("/api/v1/profile/github-data", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 204
    assert_no_user_data()
    me = client.get("/api/v1/auth/me").json()
    assert me["github_connected"] is True
    assert client.get("/api/v1/profile").status_code == 404
    event = AuditEvent.objects.get(action="github_data_deleted")
    assert event.user == user and event.outcome == "success"
    assert set(event.metadata) == {"deleted"}
    assert FACTORY_TOKEN not in caplog.text and FACTORY_TOKEN not in str(event.metadata)


def test_sync_available_again_after_data_deletion(user, everything, monkeypatch) -> None:
    SyncJob.objects.create(
        user=user, job_type="github_profile_sync", status="COMPLETED", completed_at=timezone.now()
    )
    monkeypatch.setattr("github.tasks.sync_github_profile.delay", lambda pk: None)
    client, csrf = csrf_client(user)
    client.delete("/api/v1/profile/github-data", HTTP_X_CSRFTOKEN=csrf)
    status = client.get("/api/v1/sync/status").json()
    assert status["last_synced_at"] is None  # the dashboard falls through to onboarding
    response = client.post("/api/v1/profile/sync", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 202  # no cooldown left from the deleted history


# --- DELETE /auth/account -------------------------------------------------------------


@respx.mock
def test_account_deletion(user, everything, caplog) -> None:
    grant = respx.mock.delete(GRANT_URL).respond(204)
    client, csrf = csrf_client(user)
    with caplog.at_level(logging.DEBUG):
        response = client.delete("/api/v1/auth/account", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 204
    assert grant.called
    assert not User.objects.filter(pk=user.pk).exists()
    assert not GitHubAccount.objects.exists()
    assert_no_user_data()
    assert client.get("/api/v1/auth/me").status_code == 401
    event = AuditEvent.objects.get(action="account_deleted")
    assert event.user is None and event.outcome == "success"
    assert event.metadata["revocation"] == "revoked"
    assert FACTORY_TOKEN not in caplog.text and FACTORY_TOKEN not in str(event.metadata)


@respx.mock
@pytest.mark.parametrize(
    "failure",
    [httpx.Response(500), httpx.ConnectTimeout("timed out")],
    ids=["http-500", "timeout"],
)
def test_account_deletion_when_revocation_fails(user, everything, failure, caplog) -> None:
    route = respx.mock.delete(GRANT_URL)
    if isinstance(failure, httpx.Response):
        route.mock(return_value=failure)
    else:
        route.mock(side_effect=failure)
    client, csrf = csrf_client(user)
    with caplog.at_level(logging.DEBUG):
        response = client.delete("/api/v1/auth/account", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 204
    assert not User.objects.filter(pk=user.pk).exists()
    assert_no_user_data()
    assert AuditEvent.objects.get(action="account_deleted").metadata["revocation"] == "failed"
    assert FACTORY_TOKEN not in caplog.text


@respx.mock
def test_sign_in_after_account_deletion_creates_new_account(client: Client) -> None:
    mock_github_ok(respx.mock)
    respx.mock.delete(GRANT_URL).respond(204)
    callback(client, code="oauth-code-5f3a9c", state=start(client))
    first = User.objects.get()
    client.get("/api/v1/auth/csrf/")
    response = client.delete(
        "/api/v1/auth/account", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
    )
    assert response.status_code == 204

    callback(client, code="oauth-code-5f3a9c", state=start(client))
    second = User.objects.get()
    assert second.pk != first.pk
    assert not SavedRepository.objects.exists()


# --- Disconnect -----------------------------------------------------------------------


@respx.mock
def test_disconnect_deletes_github_data(user, everything) -> None:
    respx.mock.delete(GRANT_URL).respond(204)
    client, csrf = csrf_client(user)
    response = client.post("/api/v1/auth/github/disconnect", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 200
    assert_no_user_data()
    assert User.objects.filter(pk=user.pk).exists()
    event = AuditEvent.objects.get(action="github_disconnect")
    assert event.metadata["deleted"]["saved"] == 1
    assert FACTORY_TOKEN not in str(event.metadata)


# --- CSRF and authentication ----------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/v1/profile/github-data", "/api/v1/auth/account"])
def test_deletion_requires_csrf(user, everything, path: str) -> None:
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    assert client.delete(path).status_code == 403
    assert User.objects.filter(pk=user.pk).exists()
    assert SavedRepository.objects.exists()


@pytest.mark.parametrize("path", ["/api/v1/profile/github-data", "/api/v1/auth/account"])
def test_deletion_signed_out_is_401(client: Client, path: str) -> None:
    assert client.delete(path).status_code == 401
