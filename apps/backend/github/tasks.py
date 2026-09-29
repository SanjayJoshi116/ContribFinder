import logging
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from jobs.models import SyncJob
from services.github.errors import GitHubError
from services.github.retry import Retry, decide_retry
from services.github.sync import GitHubSyncService, JobCancelled
from services.jobs import claim_job
from services.jobs import finish_job as _finish

__all__ = ["claim_job", "sync_github_profile"]

logger = logging.getLogger(__name__)
Status = SyncJob.Status


def _safe_detail(exc: Exception) -> str:
    # GitHubError messages are "GET <path> returned <status>" by construction; for anything
    # else keep only the type name so no unexpected content is stored.
    return str(exc)[:500] if isinstance(exc, GitHubError) else type(exc).__name__


@shared_task(bind=True, name="github.sync_github_profile", acks_late=True, max_retries=None)
def sync_github_profile(self: Any, job_id: int) -> None:
    """Run a GitHub profile sync job. Takes only the job ID; never a credential."""
    if not claim_job(job_id):
        logger.info("Sync job %s not claimable (duplicate, cancelled or finished)", job_id)
        return
    job = SyncJob.objects.select_related("user").get(pk=job_id)

    try:
        GitHubSyncService(job).run()
    except JobCancelled:
        logger.info("Sync job %s cancelled", job_id)
        return
    except Exception as exc:
        decision = decide_retry(
            exc,
            job.attempts,
            max_attempts=settings.SYNC_MAX_ATTEMPTS,
            max_delay=settings.GITHUB_MAX_RETRY_DELAY,
        )
        if isinstance(decision, Retry):
            moved = SyncJob.objects.filter(pk=job_id, status=Status.RUNNING).update(
                status=Status.RETRYING,
                error_detail=_safe_detail(exc),
                updated_at=timezone.now(),
            )
            if moved:
                logger.warning(
                    "Sync job %s retrying in %ss after %s",
                    job_id,
                    decision.countdown,
                    type(exc).__name__,
                )
                raise self.retry(countdown=decision.countdown) from None
            return
        logger.warning("Sync job %s failed: %s (%s)", job_id, decision.code, type(exc).__name__)
        _finish(
            job_id,
            Status.FAILED,
            error_code=decision.code,
            error_detail=_safe_detail(exc),
            completed_at=timezone.now(),
        )
        return

    _finish(job_id, Status.COMPLETED, error_code="", error_detail="", completed_at=timezone.now())
