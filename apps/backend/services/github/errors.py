"""Typed GitHub API errors, and how a GitHub response maps to one (the REST client and the
OAuth revocation share it). Messages carry status code and path only: never headers, bodies or
credentials."""

import time

import httpx

API_VERSION = "2022-11-28"
# GitHub asks clients to wait at least a minute on a secondary limit without Retry-After.
SECONDARY_LIMIT_DEFAULT_WAIT = 60
# How GitHub words a secondary limit in the error message (current and older wording).
SECONDARY_LIMIT_MARKERS = ("secondary rate limit", "abuse detection")


class GitHubError(Exception):
    """Base class for GitHub API failures."""


class GitHubAuthError(GitHubError):
    """GitHub rejected the token (401): the user must sign in again. Not retryable."""


class GitHubRateLimited(GitHubError):
    """Primary or secondary rate limit hit; ``retry_after`` is the wait in seconds."""

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class GitHubTransientError(GitHubError):
    """Timeout, connection problem or 5xx: retry with backoff."""


class GitHubNotFound(GitHubError):
    """404 for the requested resource."""


class GitHubForbidden(GitHubError):
    """403 that is not a rate limit (e.g. resource blocked)."""


class GitHubClientError(GitHubError):
    """Any other unexpected 4xx response."""


class GitHubInvalidResponse(GitHubClientError):
    """A successful response whose body is not the JSON the client expects (not JSON, a
    missing field, a wrong type)."""


class GitHubValidationError(GitHubClientError):
    """422: GitHub rejected the request as invalid (e.g. a search for a user it won't search)."""


class GitHubConflict(GitHubClientError):
    """409: e.g. listing commits of an empty repository."""


class GitHubUnavailableForLegalReasons(GitHubClientError):
    """451: the repository is blocked (e.g. DMCA takedown)."""


class GitHubGone(GitHubClientError):
    """410: e.g. listing issues of a repository with issues disabled."""


def error_for_response(response: httpx.Response, path: str, method: str = "GET") -> Exception:
    status = response.status_code
    where = f"{method} {path} returned {status}"
    if status == 401:
        return GitHubAuthError(where)
    if status in (403, 429):
        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return GitHubRateLimited(where, int(retry_after))
        if response.headers.get("X-RateLimit-Remaining") == "0":
            reset = response.headers.get("X-RateLimit-Reset", "")
            wait = (
                int(reset) - int(time.time()) if reset.isdigit() else SECONDARY_LIMIT_DEFAULT_WAIT
            )
            return GitHubRateLimited(where, max(wait, 1))
        if status == 429 or _is_secondary_limit(response):
            return GitHubRateLimited(where, SECONDARY_LIMIT_DEFAULT_WAIT)
        return GitHubForbidden(where)
    if status == 404:
        return GitHubNotFound(where)
    if status == 409:
        return GitHubConflict(where)
    if status == 410:
        return GitHubGone(where)
    if status == 451:
        return GitHubUnavailableForLegalReasons(where)
    if status == 422:
        return GitHubValidationError(where)
    if status >= 500:
        return GitHubTransientError(where)
    return GitHubClientError(where)


def _is_secondary_limit(response: httpx.Response) -> bool:
    """A 403 whose message says a secondary limit was hit (no Retry-After, requests
    remaining). The message is only inspected, never copied into the error."""
    try:
        data = response.json()
    except ValueError:
        data = None
    message = str(data.get("message", "")) if isinstance(data, dict) else response.text[:1024]
    return any(marker in message.lower() for marker in SECONDARY_LIMIT_MARKERS)
