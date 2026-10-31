"""GitHub app fixes from the review sweep (Bug_Backlog.md batch 29, change github-review-fixes)."""

import logging
from unittest.mock import patch

import pytest
import respx
from celery.exceptions import Retry
from django.contrib.admin.sites import site
from django.db import connection
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AuditEvent, User
from github.models import GitHubAccount, GitHubProfile
from github.tasks import revoke_later
from repositories.models import Repository, UserRepository
from services.crypto import encrypt_token

from .factories import GitHubAccountFactory
from .test_github_auth import GRANT_URL, TOKEN, assert_no_secrets

pytestmark = pytest.mark.django_db

Relation = UserRepository.Relation


def link(user: User, ids: range, relation: str = Relation.OWNER) -> None:
    """Repositories ``octocat/r<id>`` linked to ``user``: two queries however many."""
    now = timezone.now()
    repos = Repository.objects.bulk_create(
        Repository(
            github_id=n,
            owner_login="octocat",
            name=f"r{n}",
            full_name=f"octocat/r{n}",
            html_url=f"https://github.com/octocat/r{n}",
            pushed_at=now,
            synced_at=now,
        )
        for n in ids
    )
    UserRepository.objects.bulk_create(
        UserRepository(user=user, repository=r, relation=relation) for r in repos
    )


def make_profile(user: User) -> GitHubProfile:
    return GitHubProfile.objects.create(
        user=user, github_id=user.pk, login=user.username, synced_at=timezone.now()
    )


@pytest.fixture
def staff() -> User:
    return User.objects.create(username="admin", is_staff=True, is_superuser=True)


# --- Delete-data is one transaction (GH-3) ----------------------------------------------


def test_a_failing_audit_write_keeps_the_github_data(
    signed_in_client: APIClient, user: User
) -> None:
    link(user, range(1, 2))
    make_profile(user)

    signed_in_client.raise_request_exception = False
    with patch("services.audit.record", side_effect=RuntimeError("audit down")):
        response = signed_in_client.delete("/api/v1/profile/github-data")

    assert response.status_code == 500
    assert GitHubProfile.objects.filter(user=user).exists()
    assert UserRepository.objects.filter(user=user).exists()
    assert not AuditEvent.objects.filter(action="github_data_deleted").exists()


def test_deleting_github_data_still_records_it(signed_in_client: APIClient, user: User) -> None:
    link(user, range(1, 2))
    response = signed_in_client.delete("/api/v1/profile/github-data")
    assert response.status_code == 204
    assert not UserRepository.objects.filter(user=user).exists()
    event = AuditEvent.objects.get(action="github_data_deleted")
    assert event.user == user and set(event.metadata) == {"deleted"}


# --- Revocation task (GH-1, GH-5) -------------------------------------------------------


@respx.mock
def test_eager_revocation_is_not_retried_inline(caplog: pytest.LogCaptureFixture) -> None:
    route = respx.mock.delete(GRANT_URL).respond(503)
    revoke_later.apply(args=(encrypt_token(TOKEN), None, True), throw=True)
    assert route.call_count == 1  # no inline retry inside the request
    event = AuditEvent.objects.get(action="github_revocation_failed")
    assert event.metadata == {"reason": "github_unavailable"}
    assert not any(r.exc_info for r in caplog.records)  # a GitHub error needs no traceback


@respx.mock
@override_settings(CELERY_TASK_ALWAYS_EAGER=False)  # with a worker
def test_revocation_with_a_worker_is_retried() -> None:
    route = respx.mock.delete(GRANT_URL).respond(503)
    with pytest.raises(Retry):
        revoke_later.apply(args=(encrypt_token(TOKEN), None, True), throw=True)
    assert route.call_count == 1
    assert not AuditEvent.objects.filter(action="github_revocation_failed").exists()


def test_an_unexpected_error_keeps_its_traceback(caplog: pytest.LogCaptureFixture) -> None:
    with (
        caplog.at_level(logging.DEBUG),
        patch("github.tasks.revoke", side_effect=ValueError("bug in revoke")),
    ):
        revoke_later.apply(args=(encrypt_token(TOKEN), None, True), throw=True)

    record = next(r for r in caplog.records if r.message == "GitHub revocation failed unexpectedly")
    assert record.exc_info is not None and record.exc_info[0] is ValueError
    event = AuditEvent.objects.get(action="github_revocation_failed")
    assert event.metadata == {"reason": "internal_error"}
    assert_no_secrets(caplog.text)
    assert all(TOKEN not in r.getMessage() for r in caplog.records)


# --- Admins (GH-2, GH-8) ----------------------------------------------------------------


@pytest.mark.parametrize("model", [GitHubAccount, GitHubProfile])
def test_github_admins_cannot_add_or_delete(model: type, staff: User) -> None:
    request = RequestFactory().get("/admin/")
    request.user = staff
    admin = site._registry[model]
    assert not admin.has_add_permission(request)
    assert not admin.has_delete_permission(request)
    assert admin.list_select_related == ("user",)


@pytest.mark.parametrize(
    ("model", "url"),
    [
        (GitHubAccount, "/admin/github/githubaccount/"),
        (GitHubProfile, "/admin/github/githubprofile/"),
    ],
)
def test_github_admin_changelists_query_users_once(model: type, url: str, staff: User) -> None:
    client = APIClient()
    client.force_login(staff)

    def make_rows(n: int) -> None:
        for _ in range(n):
            account = GitHubAccountFactory.create()
            if model is GitHubProfile:
                make_profile(account.user)

    def count() -> int:
        with CaptureQueriesContext(connection) as queries:
            assert client.get(url).status_code == 200
        return len(queries)

    make_rows(1)
    one = count()
    make_rows(3)
    assert count() == one


# --- Owned-repository list (GH-4, GH-7) -------------------------------------------------


def test_owned_repositories_listed_once_without_contributions(
    signed_in_client: APIClient, user: User
) -> None:
    link(user, range(1, 3))
    UserRepository.objects.create(
        user=user, repository=Repository.objects.get(github_id=1), relation=Relation.CONTRIBUTOR
    )
    link(user, range(3, 4), Relation.CONTRIBUTOR)
    body = signed_in_client.get("/api/v1/profile/repositories").json()
    assert body["count"] == 2
    assert sorted(r["name"] for r in body["results"]) == ["r1", "r2"]


@override_settings(GITHUB_SYNC_MAX_REPOS=200)
def test_the_page_cap_follows_the_sync_cap(signed_in_client: APIClient, user: User) -> None:
    link(user, range(1, 151))
    body = signed_in_client.get("/api/v1/profile/repositories?page_size=200").json()
    assert body["count"] == 150 and len(body["results"]) == 150 and body["next"] is None
    link(user, range(151, 211))
    capped = signed_in_client.get("/api/v1/profile/repositories?page_size=1000").json()
    assert len(capped["results"]) == 200  # the cap is the sync cap


@override_settings(GITHUB_SYNC_MAX_REPOS=10)
def test_the_page_cap_is_never_below_100(signed_in_client: APIClient, user: User) -> None:
    link(user, range(1, 101))
    body = signed_in_client.get("/api/v1/profile/repositories?page_size=100").json()
    assert len(body["results"]) == 100
