"""Account fixes from the review sweep (Bug_Backlog.md batch 28, change accounts-review-fixes)."""

from datetime import timedelta
from unittest.mock import patch

import pytest
import respx
from django.contrib.admin.sites import site
from django.contrib.sessions.models import Session
from django.test import Client, RequestFactory
from django.utils import timezone
from kombu.exceptions import OperationalError as BrokerError

from accounts.models import AuditEvent, User
from accounts.tasks import clear_expired_sessions
from github.models import GitHubAccount
from github.tasks import revoke_later
from jobs.models import SyncJob
from services.crypto import encrypt_token
from services.github.retry import Fail

from .factories import UserFactory
from .test_github_auth import (
    CODE,
    GRANT_URL,
    IDENTITY,
    TOKEN,
    _assert_auth_error_redirect,
    assert_no_secrets,
    callback,
    mock_github_ok,
    start,
)

pytestmark = pytest.mark.django_db


# --- Deactivated user (ACC-1) ----------------------------------------------------------


@respx.mock
def test_a_deactivated_user_is_refused_before_anything_is_stored(
    client: Client, django_capture_on_commit_callbacks
) -> None:
    mock_github_ok(respx.mock)
    UserFactory.create(username=f"gh_{IDENTITY['id']}", is_active=False)

    with (
        patch("github.tasks.revoke_later.delay") as revoke,
        django_capture_on_commit_callbacks(execute=True),
    ):
        response = callback(client, code=CODE, state=start(client))

    _assert_auth_error_redirect(response, "failed")
    assert not GitHubAccount.objects.exists()
    assert not SyncJob.objects.exists()
    assert "_auth_user_id" not in client.session
    revoke.assert_called_once()
    encrypted, github_id, grant = revoke.call_args.args
    assert (github_id, grant) == (None, True)  # the deactivated user's whole grant
    assert_no_secrets(encrypted)  # only ciphertext is queued
    event = AuditEvent.objects.get(action="sign_in_failed")
    assert event.metadata["reason"] == "account_inactive"


# --- Unexpected error while linking (ACC-2) ----------------------------------------------


@respx.mock
def test_an_error_while_linking_redirects_instead_of_a_server_error(
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    mock_github_ok(respx.mock)
    with patch("accounts.views.link_github_account", side_effect=RuntimeError("db gone")):
        response = callback(client, code=CODE, state=start(client))

    _assert_auth_error_redirect(response, "failed")
    assert "_auth_user_id" not in client.session
    assert AuditEvent.objects.get(action="sign_in_failed").metadata["reason"] == "internal_error"
    assert "RuntimeError" in caplog.text
    assert_no_secrets(caplog.text)


# --- The callback is never throttled (ACC-6) ---------------------------------------------


def test_the_callback_never_answers_429(client: Client) -> None:
    statuses = {client.get("/api/v1/auth/github/callback").status_code for _ in range(12)}
    assert statuses == {302}


# --- Read-only audit admin (ACC-5, ACC-10) ------------------------------------------------


def test_staff_cannot_add_or_delete_audit_entries() -> None:
    request = RequestFactory().get("/admin/")
    request.user = User.objects.create(username="admin", is_staff=True, is_superuser=True)
    admin = site._registry[AuditEvent]
    assert not admin.has_add_permission(request)
    assert not admin.has_delete_permission(request)
    assert admin.list_select_related == ("user",)


# --- Expired sessions (ACC-7) --------------------------------------------------------------


def test_expired_sessions_are_cleared() -> None:
    now = timezone.now()
    Session.objects.create(session_key="old", session_data="", expire_date=now - timedelta(days=1))
    Session.objects.create(session_key="new", session_data="", expire_date=now + timedelta(days=1))
    clear_expired_sessions()
    assert list(Session.objects.values_list("session_key", flat=True)) == ["new"]


def test_session_cleanup_is_scheduled(settings) -> None:
    tasks = {entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()}
    assert "accounts.clear_expired_sessions" in tasks


# --- Queued revocation (ACC-11, ACC-12, ACC-14, ACC-15, ACC-16, ACC-19) -----------------------

GRANT = GRANT_URL
GITHUB_ID = 424242
assert IDENTITY["id"] == GITHUB_ID
TOKEN_ENDPOINT = GRANT_URL.removesuffix("grant") + "token"


@respx.mock
def test_a_late_revocation_spares_a_user_who_signed_in_again() -> None:
    grant = respx.mock.delete(GRANT).respond(204)
    token = respx.mock.delete(TOKEN_ENDPOINT).respond(204)
    user = UserFactory.create(username=f"gh_{GITHUB_ID}")
    GitHubAccount.objects.create(
        user=user,
        github_id=GITHUB_ID,
        username="octocat",
        access_token_encrypted=encrypt_token("gho_new_token_after_sign_in_0000"),
    )
    revoke_later.apply(args=(encrypt_token("gho_old_token_before_disconnect"), GITHUB_ID, True))
    assert not grant.called  # the grant is in use again
    assert token.called  # only the old token goes


@respx.mock
def test_a_token_still_stored_is_never_revoked() -> None:
    route = respx.mock.delete(TOKEN_ENDPOINT).respond(204)
    user = UserFactory.create(username=f"gh_{GITHUB_ID}")
    stored = encrypt_token(TOKEN)
    GitHubAccount.objects.create(
        user=user, github_id=GITHUB_ID, username="octocat", access_token_encrypted=stored
    )
    revoke_later.apply(args=(stored, GITHUB_ID, False))
    assert not route.called


@respx.mock
def test_a_permanent_failure_is_audited_not_retried(caplog: pytest.LogCaptureFixture) -> None:
    route = respx.mock.delete(GRANT).respond(422)
    revoke_later.apply(args=(encrypt_token(TOKEN), None, True), throw=True)
    assert route.call_count == 1
    event = AuditEvent.objects.get(action="github_revocation_failed")
    assert event.user is None and event.metadata == {"reason": "internal_error"}
    assert_no_secrets(caplog.text + str(event.metadata))
    assert not any(r.exc_info for r in caplog.records)  # GitHub refusing is not a bug


@respx.mock
def test_retries_end_in_an_audited_failure() -> None:
    respx.mock.delete(GRANT).respond(503)
    # The shared policy says the attempts are used up (it is tested on its own).
    with patch("github.tasks.decide_retry", return_value=Fail("github_unavailable")):
        revoke_later.apply(args=(encrypt_token(TOKEN), None, True), throw=True)
    event = AuditEvent.objects.get(action="github_revocation_failed")
    assert event.metadata == {"reason": "github_unavailable"}


def test_a_removed_key_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    revoke_later.apply(args=("not-a-fernet-token", None, True), throw=True)
    assert "encryption key was removed" in caplog.text


def test_a_broker_failure_never_stops_a_disconnect(
    user: User, django_capture_on_commit_callbacks
) -> None:
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    client.get("/api/v1/auth/csrf/")
    with (
        patch("github.tasks.revoke_later.delay", side_effect=BrokerError("broker down")),
        django_capture_on_commit_callbacks(execute=True),
    ):
        response = client.post(
            "/api/v1/auth/github/disconnect", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
        )
    assert response.status_code == 200
    assert response.json() == {"revocation": "queued"}
    assert not GitHubAccount.objects.filter(user=user).exists()
    assert AuditEvent.objects.filter(action="github_disconnect").exists()


@respx.mock
def test_a_broker_failure_on_a_refused_sign_in_still_redirects(
    client: Client, django_capture_on_commit_callbacks
) -> None:
    mock_github_ok(respx.mock)
    User.objects.create(username=f"gh_{GITHUB_ID}", is_active=False)
    with (
        patch("github.tasks.revoke_later.delay", side_effect=BrokerError("broker down")),
        django_capture_on_commit_callbacks(execute=True),
    ):
        response = callback(client, code=CODE, state=start(client))
    _assert_auth_error_redirect(response, "failed")
