"""Typed GitHub API errors. Messages carry status code and path only: never headers,
bodies or credentials."""


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


class GitHubValidationError(GitHubClientError):
    """422: GitHub rejected the request as invalid (e.g. a search for a user it won't search)."""


class GitHubConflict(GitHubClientError):
    """409: e.g. listing commits of an empty repository."""


class GitHubUnavailableForLegalReasons(GitHubClientError):
    """451: the repository is blocked (e.g. DMCA takedown)."""
