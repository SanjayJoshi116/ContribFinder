"""Retry policy for GitHub sync jobs (design D4). Pure: easy to test, no Celery."""

import random
from collections.abc import Callable
from dataclasses import dataclass

from services.errors import INTERNAL_ERROR, PermanentJobError

from .errors import (
    GitHubAuthError,
    GitHubError,
    GitHubRateLimited,
    GitHubTransientError,
)

BACKOFF_BASE_SECONDS = 30
BACKOFF_MAX_SECONDS = 600


@dataclass(frozen=True)
class Retry:
    countdown: int


@dataclass(frozen=True)
class Fail:
    code: str


def attempt_number(executed: int, max_attempts: int, *, eager: bool) -> int:
    """The attempt to decide on. Without a worker (eager mode) the first try is the last: a
    retry would run inline, inside the request, with no backoff."""
    return max_attempts if eager else executed


def decide_retry(
    error: Exception,
    attempts: int,
    *,
    max_attempts: int,
    max_delay: int,
    rng: Callable[[], float] = random.random,
) -> Retry | Fail:
    """Decide what to do after ``error`` on execution number ``attempts`` (1-based)."""
    if isinstance(error, PermanentJobError):
        return Fail(error.code)
    if isinstance(error, GitHubAuthError):
        return Fail("github_auth_invalid")
    if isinstance(error, GitHubRateLimited):
        if error.retry_after > max_delay or attempts >= max_attempts:
            return Fail("github_rate_limited")
        return Retry(error.retry_after + 1 + int(rng() * 5))
    if isinstance(error, GitHubTransientError):
        if attempts >= max_attempts:
            return Fail("github_unavailable")
        backoff = min(BACKOFF_BASE_SECONDS * 2 ** (attempts - 1), BACKOFF_MAX_SECONDS)
        return Retry(backoff + int(rng() * backoff * 0.2))
    if isinstance(error, GitHubError):
        return Fail("github_error")
    return Fail(INTERNAL_ERROR)
