"""GitHub OAuth App flow: authorize URL, code exchange, identity, grant revocation.

Only this module talks to GitHub's OAuth endpoints. Exceptions carry a stable ``code``
and a message that never includes the authorization code, token or client secret.
"""

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from django.conf import settings

from services.github.errors import (
    API_VERSION,
    GitHubRateLimited,
    GitHubTransientError,
    error_for_response,
)
from services.github.text import parse_json


class OAuthError(Exception):
    """GitHub OAuth step failed. ``code`` is safe to log and surface to the client."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TokenResult:
    access_token: str
    scopes: str

    def __repr__(self) -> str:
        return f"TokenResult(access_token=<redacted>, scopes={self.scopes!r})"


@dataclass(frozen=True)
class GitHubIdentity:
    github_id: int
    login: str
    name: str
    avatar_url: str


def has_app_credentials() -> bool:
    """Whether the OAuth app's client credentials are configured (sign-in and the app-level
    GitHub client both need them)."""
    return bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET)


def _client() -> httpx.Client:
    return httpx.Client(timeout=settings.GITHUB_HTTP_TIMEOUT)


def _api_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
        "scope": " ".join(settings.GITHUB_OAUTH_SCOPES),
        "state": state,
        "allow_signup": "true",
    }
    return f"{settings.GITHUB_OAUTH_BASE_URL}/login/oauth/authorize?{urlencode(params)}"


def exchange_code(code: str) -> TokenResult:
    try:
        with _client() as client:
            response = client.post(
                f"{settings.GITHUB_OAUTH_BASE_URL}/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
                },
            )
    except httpx.HTTPError as exc:
        raise OAuthError(
            "github_unavailable", f"Token exchange failed: {type(exc).__name__}"
        ) from None

    if response.status_code != 200:
        raise OAuthError("token_exchange_failed", f"Token endpoint returned {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        raise OAuthError("token_exchange_failed", "Token endpoint returned non-JSON") from None
    # GitHub reports exchange errors with HTTP 200 and an ``error`` field.
    if "error" in payload or not payload.get("access_token"):
        error = str(payload.get("error", "missing_access_token"))
        raise OAuthError("token_exchange_failed", f"Token exchange rejected: {error}")
    return TokenResult(access_token=payload["access_token"], scopes=payload.get("scope", ""))


def fetch_identity(access_token: str) -> GitHubIdentity:
    try:
        with _client() as client:
            response = client.get(
                f"{settings.GITHUB_API_BASE_URL}/user", headers=_api_headers(access_token)
            )
    except httpx.HTTPError as exc:
        raise OAuthError(
            "github_unavailable", f"Identity fetch failed: {type(exc).__name__}"
        ) from None
    if response.status_code != 200:
        raise OAuthError("identity_failed", f"GET /user returned {response.status_code}")
    try:
        data = parse_json(response.text)  # stored as the display name (spec "Stored GitHub text")
        login = data["login"]
        identity = GitHubIdentity(
            github_id=int(data["id"]),
            login=login if isinstance(login, str) else "",  # null or a number is no login
            name=str(data.get("name") or ""),
            avatar_url=str(data.get("avatar_url") or ""),
        )
    except (ValueError, TypeError, KeyError, AttributeError):
        identity = None  # not JSON, not an object, or a field missing or malformed
    if identity is None or not identity.login:
        raise OAuthError("identity_failed", "GET /user returned an unexpected body")
    return identity


def revoke_grant(access_token: str) -> None:
    """Revoke the OAuth grant (all tokens for this app/user pair). Raises
    ``GitHubRateLimited`` for a rate limit, ``GitHubTransientError`` for another temporary
    failure, ``OAuthError`` otherwise."""
    _revoke("grant", access_token)


def revoke_token(access_token: str) -> None:
    """Revoke this one token; other tokens of the grant stay valid. Raises as
    ``revoke_grant``."""
    _revoke("token", access_token)


def _revoke(kind: str, access_token: str) -> None:
    try:
        with _client() as client:
            response = client.request(
                "DELETE",
                f"{settings.GITHUB_API_BASE_URL}/applications/{settings.GITHUB_CLIENT_ID}/{kind}",
                auth=(settings.GITHUB_CLIENT_ID, settings.GITHUB_CLIENT_SECRET),
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": API_VERSION,
                },
                json={"access_token": access_token},
            )
    except httpx.HTTPError as exc:
        raise GitHubTransientError(f"Revocation failed: {type(exc).__name__}") from None
    if response.status_code >= 500:
        raise GitHubTransientError(f"Revocation returned {response.status_code}")
    if response.status_code in (403, 429):
        # A rate limit (the app credentials are shared with the background refresh) is
        # retried with its wait; any other 403 is final (GHS-4).
        error = error_for_response(response, f"/applications/{kind}", "DELETE")
        if isinstance(error, GitHubRateLimited):
            raise error
    # 404 means it is already gone, which is the state we want.
    if response.status_code not in (204, 404):
        raise OAuthError("revocation_failed", f"Revocation returned {response.status_code}")
