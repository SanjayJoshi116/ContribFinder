import logging
from typing import Any

from celery import shared_task
from django.conf import settings

from jobs.models import SyncJob
from services.data_deletion import purge_user_github_cache
from services.github.accounts import record_revocation_failure, revoke
from services.github.oauth import OAuthError
from services.github.retry import Retry, attempt_number, decide_retry
from services.github.sync import GitHubSyncService
from services.jobs import claim_job, run_tracked_job, start_discovery_after

__all__ = [
    "claim_job",
    "purge_user_cache",
    "revoke_later",
    "revoke_replaced_token",
    "sync_github_profile",
]

logger = logging.getLogger(__name__)


def _run(job: SyncJob) -> None:
    GitHubSyncService(job).run()


@shared_task(bind=True, name="github.sync_github_profile", acks_late=True, max_retries=None)
def sync_github_profile(self: Any, job_id: int) -> None:
    """Run a GitHub profile sync job. Takes only the job ID; never a credential. A completed
    sync starts repository discovery (Phase 4)."""
    run_tracked_job(self, job_id, _run, on_completed=start_discovery_after)


# First try plus retries of a queued revocation.
REVOCATION_ATTEMPTS = 4


@shared_task(bind=True, name="github.revoke_later", acks_late=True, max_retries=None)
def revoke_later(self: Any, encrypted: str, github_id: int | None, grant: bool) -> None:
    """Revoke a GitHub grant or token (disconnect, account deletion, a replaced or refused
    token). Takes the token encrypted only: useless without the server's keys. Temporary
    failures are retried by the shared policy; a final failure is audited without the token.
    Without a worker (eager mode) the first try is the last, as for tracked jobs: no inline
    retries inside the request."""
    try:
        revoke(encrypted, github_id, grant=grant)
    except Exception as exc:
        decision = decide_retry(
            exc,
            attempt_number(
                self.request.retries + 1,
                REVOCATION_ATTEMPTS,
                eager=settings.CELERY_TASK_ALWAYS_EAGER,
            ),
            max_attempts=REVOCATION_ATTEMPTS,
            max_delay=settings.GITHUB_MAX_RETRY_DELAY,
        )
        if isinstance(decision, Retry):
            raise self.retry(countdown=decision.countdown) from None
        if decision.code == "internal_error" and not isinstance(exc, OAuthError):
            # A bug, not GitHub refusing (OAuthError): keep the traceback. The task holds
            # ciphertext only, and ``revoke`` raises nothing that carries the plaintext.
            logger.exception("GitHub revocation failed unexpectedly")
        record_revocation_failure(decision.code)


@shared_task(name="github.purge_user_cache", acks_late=True)
def purge_user_cache(user_id: int) -> None:
    """The delayed second purge after a GitHub data deletion (``data_deletion``)."""
    purge_user_github_cache(user_id)


@shared_task(name="github.revoke_replaced_token", acks_late=True)
def revoke_replaced_token(github_id: int, previous_encrypted: str) -> None:
    """Messages queued before 0.12.41; new ones use ``revoke_later``."""
    revoke_later.delay(previous_encrypted, github_id, False)
