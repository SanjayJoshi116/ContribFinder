import logging
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from django.conf import settings
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AuditEvent, User
from accounts.views import OAUTH_STATE_SESSION_KEY
from github.models import GitHubAccount
from services.crypto import decrypt_token

pytestmark = pytest.mark.django_db

TOKEN = "gho_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
CODE = "oauth-code-5f3a9c"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"
GRANT_URL = f"https://api.github.com/applications/{settings.GITHUB_CLIENT_ID}/grant"
IDENTITY = {"id": 424242, "login": "octocat", "name": "The Octocat", "avatar_url": "https://a/1"}

SECRETS = (TOKEN, CODE, settings.GITHUB_CLIENT_SECRET)


def start(client: Client) -> str:
    response = client.get("/api/v1/auth/github")
    assert response.status_code == 302
    return parse_qs(urlparse(response["Location"]).query)["state"][0]


def callback(client: Client, **params: str):
    return client.get("/api/v1/auth/github/callback", params)


def mock_github_ok(router: respx.MockRouter, identity: dict[str, object] | None = None) -> None:
    router.post(TOKEN_URL).respond(
        200, json={"access_token": TOKEN, "scope": "", "token_type": "bearer"}
    )
    router.get(USER_URL).respond(200, json=identity or IDENTITY)


def assert_no_secrets(text: str) -> None:
    for secret in SECRETS:
        assert secret not in text


# --- Sign-in start -----------------------------------------------------------


def test_start_redirects_to_github_with_state_and_no_scopes(client: Client) -> None:
    response = client.get("/api/v1/auth/github")
    assert response.status_code == 302
    location = urlparse(response["Location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == (
        "https://github.com/login/oauth/authorize"
    )
    query = parse_qs(location.query, keep_blank_values=True)
    assert query["client_id"] == [settings.GITHUB_CLIENT_ID]
    assert query["redirect_uri"] == [settings.GITHUB_OAUTH_REDIRECT_URI]
    assert query["scope"] == [""]
    assert len(query["state"][0]) >= 32
    assert client.session[OAUTH_STATE_SESSION_KEY] == query["state"][0]


def test_each_start_issues_a_new_state(client: Client) -> None:
    assert start(client) != start(client)


# --- Callback success -----------------------------------------------------------


@respx.mock
def test_first_time_sign_in_creates_user_and_account(client: Client) -> None:
    mock_github_ok(respx.mock)
    state = start(client)

    response = callback(client, code=CODE, state=state)

    assert response.status_code == 302
    assert response["Location"] == f"{settings.FRONTEND_URL}{settings.FRONTEND_SIGNED_IN_PATH}"
    user = User.objects.get(username="gh_424242")
    assert user.display_name == "The Octocat"
    assert not user.has_usable_password()
    account = GitHubAccount.objects.get(github_id=424242)
    assert account.user == user
    assert account.username == "octocat"
    assert account.avatar_url == "https://a/1"
    # Session established.
    assert client.get("/api/v1/auth/me").status_code == 200
    assert AuditEvent.objects.filter(action="sign_in", outcome="success", user=user).exists()


@respx.mock
def test_stored_token_is_encrypted(client: Client) -> None:
    mock_github_ok(respx.mock)
    callback(client, code=CODE, state=start(client))
    account = GitHubAccount.objects.get(github_id=424242)
    assert account.access_token_encrypted != TOKEN
    assert TOKEN not in account.access_token_encrypted
    assert decrypt_token(account.access_token_encrypted) == TOKEN


@respx.mock
def test_returning_user_is_updated_not_duplicated(client: Client) -> None:
    mock_github_ok(respx.mock)
    callback(client, code=CODE, state=start(client))

    other = Client()
    respx.mock.get(USER_URL).respond(
        200, json={**IDENTITY, "login": "octo-renamed", "avatar_url": "https://a/2"}
    )
    callback(other, code=CODE, state=start(other))

    assert User.objects.count() == 1
    assert GitHubAccount.objects.count() == 1
    account = GitHubAccount.objects.get()
    assert account.username == "octo-renamed"
    assert account.avatar_url == "https://a/2"


@respx.mock
def test_session_key_rotates_on_login(client: Client) -> None:
    mock_github_ok(respx.mock)
    start(client)
    pre_login_key = client.session.session_key
    callback(client, code=CODE, state=client.session[OAUTH_STATE_SESSION_KEY])
    assert client.session.session_key != pre_login_key


# --- Callback failures ------------------------------------------------------------


def _assert_auth_error_redirect(response, code: str) -> None:
    assert response.status_code == 302
    assert response["Location"] == f"{settings.FRONTEND_URL}/?auth_error={code}"


@pytest.mark.respx(assert_all_called=False)
@pytest.mark.parametrize("scenario", ["missing", "mismatched"])
def test_invalid_state_rejected_without_calling_github(
    client: Client, scenario: str, respx_mock: respx.MockRouter
) -> None:
    token_route = respx_mock.post(TOKEN_URL)
    start(client)
    params = {"code": CODE} if scenario == "missing" else {"code": CODE, "state": "forged"}

    response = callback(client, **params)

    _assert_auth_error_redirect(response, "invalid_state")
    assert not token_route.called
    assert not User.objects.exists()
    assert AuditEvent.objects.filter(action="sign_in_failed", outcome="failure").exists()


@pytest.mark.respx(assert_all_called=False)
def test_reused_state_rejected(client: Client, respx_mock: respx.MockRouter) -> None:
    mock_github_ok(respx_mock)
    state = start(client)
    callback(client, code=CODE, state=state)
    client.logout()
    calls_before = respx_mock.calls.call_count

    response = callback(client, code=CODE, state=state)

    _assert_auth_error_redirect(response, "invalid_state")
    assert respx_mock.calls.call_count == calls_before


def test_state_without_session_rejected(client: Client) -> None:
    response = callback(Client(), code=CODE, state="anything")
    _assert_auth_error_redirect(response, "invalid_state")


def test_access_denied_is_cancelled(client: Client) -> None:
    state = start(client)
    response = callback(client, error="access_denied", state=state)
    _assert_auth_error_redirect(response, "cancelled")
    assert client.get("/api/v1/auth/me").status_code == 401


@respx.mock
def test_token_exchange_rejected(client: Client) -> None:
    respx.mock.post(TOKEN_URL).respond(200, json={"error": "bad_verification_code"})
    response = callback(client, code=CODE, state=start(client))
    _assert_auth_error_redirect(response, "failed")
    assert not User.objects.exists()


@respx.mock
def test_token_exchange_timeout(client: Client, caplog: pytest.LogCaptureFixture) -> None:
    respx.mock.post(TOKEN_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))
    with caplog.at_level(logging.DEBUG):
        response = callback(client, code=CODE, state=start(client))
    _assert_auth_error_redirect(response, "failed")
    assert not User.objects.exists()
    assert_no_secrets(caplog.text)
    event = AuditEvent.objects.get(action="sign_in_failed")
    assert event.metadata["reason"] == "github_unavailable"


@respx.mock
def test_identity_fetch_failure(client: Client) -> None:
    respx.mock.post(TOKEN_URL).respond(200, json={"access_token": TOKEN, "scope": ""})
    respx.mock.get(USER_URL).respond(500)
    response = callback(client, code=CODE, state=start(client))
    _assert_auth_error_redirect(response, "failed")
    assert not GitHubAccount.objects.exists()


@respx.mock
def test_sign_in_logs_and_audit_contain_no_secrets(
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    mock_github_ok(respx.mock)
    with caplog.at_level(logging.DEBUG):
        callback(client, code=CODE, state=start(client))
        client.get("/api/v1/auth/me")
    assert_no_secrets(caplog.text)
    for event in AuditEvent.objects.all():
        assert_no_secrets(str(event.metadata))


def test_sign_in_endpoints_are_throttled(client: Client) -> None:
    statuses = [client.get("/api/v1/auth/github").status_code for _ in range(12)]
    assert statuses[:10] == [302] * 10
    assert statuses[-1] == 429


# --- Session / me -----------------------------------------------------------------


def test_me_signed_in(signed_in_client: APIClient, github_account: GitHubAccount) -> None:
    response = signed_in_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json() == {
        "id": github_account.user.pk,
        "github_username": github_account.username,
        "display_name": github_account.user.display_name,
        "avatar_url": github_account.avatar_url,
        "github_connected": True,
    }


def test_me_signed_out(api_client: APIClient) -> None:
    response = api_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_responses_never_contain_token(signed_in_client: APIClient) -> None:
    for path in ("/api/v1/auth/me", "/api/v1/auth/csrf/"):
        assert_no_secrets(signed_in_client.get(path).content.decode())
    assert "access_token" not in signed_in_client.get("/api/v1/auth/me").content.decode()


@respx.mock
def test_session_cookie_attributes(client: Client) -> None:
    mock_github_ok(respx.mock)
    response = callback(client, code=CODE, state=start(client))
    cookie = response.cookies[settings.SESSION_COOKIE_NAME]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"


def test_production_cookies_are_secure(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    monkeypatch.setenv("REDIS_URL", "redis://prod-redis:6379/0")
    production = importlib.reload(importlib.import_module("config.settings.production"))

    assert production.SESSION_COOKIE_SECURE is True
    assert production.CSRF_COOKIE_SECURE is True
    assert production.SECURE_HSTS_SECONDS > 0


def test_production_requires_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    from django.core.exceptions import ImproperlyConfigured

    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(ImproperlyConfigured, match="REDIS_URL"):
        importlib.reload(importlib.import_module("config.settings.production"))


def test_expired_session_is_unauthenticated(user: User) -> None:
    client = Client()
    client.force_login(user)
    session = client.session
    session.set_expiry(timezone.now() - timedelta(seconds=1))
    session.save()
    assert client.get("/api/v1/auth/me").status_code == 401


# --- Logout -------------------------------------------------------------------------


def _csrf_signed_in_client(user: User) -> tuple[Client, str]:
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    client.get("/api/v1/auth/csrf/")
    return client, client.cookies["csrftoken"].value


def test_logout_invalidates_session_and_keeps_account(user: User) -> None:
    client, csrf = _csrf_signed_in_client(user)
    old_session_cookie = client.cookies[settings.SESSION_COOKIE_NAME].value

    response = client.post("/api/v1/auth/logout", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == 204
    replay = Client()
    replay.cookies[settings.SESSION_COOKIE_NAME] = old_session_cookie
    assert replay.get("/api/v1/auth/me").status_code == 401
    assert GitHubAccount.objects.filter(user=user).exists()
    assert AuditEvent.objects.filter(action="logout", user=user).exists()


def test_logout_without_csrf_rejected(csrf_client: APIClient, user: User) -> None:
    csrf_client.force_login(user)
    response = csrf_client.post("/api/v1/auth/logout")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


# --- Disconnect -----------------------------------------------------------------------


@respx.mock
def test_disconnect_revokes_deletes_and_logs_out(user: User) -> None:
    grant = respx.mock.delete(GRANT_URL).respond(204)
    client, csrf = _csrf_signed_in_client(user)

    response = client.post("/api/v1/auth/github/disconnect", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == 200
    assert response.json() == {"revocation": "revoked"}
    assert grant.called
    request = grant.calls.last.request
    assert request.headers["Authorization"].startswith("Basic ")
    assert not GitHubAccount.objects.filter(user=user).exists()
    assert User.objects.filter(pk=user.pk).exists()
    assert client.get("/api/v1/auth/me").status_code == 401
    event = AuditEvent.objects.get(action="github_disconnect")
    assert event.metadata["revocation"] == "revoked"
    assert set(event.metadata) == {"revocation", "deleted"}


@respx.mock
@pytest.mark.parametrize(
    "failure",
    [httpx.Response(500), httpx.ConnectTimeout("timed out")],
    ids=["http-500", "timeout"],
)
def test_disconnect_when_github_revocation_fails(
    user: User, failure: httpx.Response | Exception, caplog: pytest.LogCaptureFixture
) -> None:
    route = respx.mock.delete(GRANT_URL)
    if isinstance(failure, httpx.Response):
        route.mock(return_value=failure)
    else:
        route.mock(side_effect=failure)
    client, csrf = _csrf_signed_in_client(user)

    with caplog.at_level(logging.DEBUG):
        response = client.post("/api/v1/auth/github/disconnect", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == 200
    assert response.json() == {"revocation": "failed"}
    assert not GitHubAccount.objects.filter(user=user).exists()
    assert client.get("/api/v1/auth/me").status_code == 401
    assert AuditEvent.objects.get(action="github_disconnect").metadata["revocation"] == "failed"
    assert_no_secrets(caplog.text)


def test_disconnect_without_csrf_rejected(csrf_client: APIClient, user: User) -> None:
    csrf_client.force_login(user)
    response = csrf_client.post("/api/v1/auth/github/disconnect")
    assert response.status_code == 403
    assert GitHubAccount.objects.filter(user=user).exists()


@respx.mock
def test_sign_in_after_disconnect_relinks_same_user(client: Client) -> None:
    mock_github_ok(respx.mock)
    respx.mock.delete(GRANT_URL).respond(204)
    callback(client, code=CODE, state=start(client))
    user = User.objects.get()
    client.post("/api/v1/auth/github/disconnect")
    assert not GitHubAccount.objects.exists()

    callback(client, code=CODE, state=start(client))

    assert User.objects.count() == 1
    assert GitHubAccount.objects.get().user == user
