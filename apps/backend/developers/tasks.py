import logging
from typing import Any

from celery import shared_task
from django.utils import timezone

from jobs.models import SyncJob
from services.jobs import claim_job, finish_job
from services.profiling.analysis import ProfileAnalysisError, ProfileAnalysisService

logger = logging.getLogger(__name__)
Status = SyncJob.Status


@shared_task(bind=True, name="developers.extract_developer_skills", acks_late=True)
def extract_developer_skills(self: Any, job_id: int) -> None:
    """Re-analyze a user's profile from stored data (job type ``profile_analysis``).

    Analysis is deterministic and makes no GitHub requests, so failures are not retried:
    the job fails with ``analysis_failed`` and the previous profile stays in place."""
    if not claim_job(job_id):
        logger.info("Analysis job %s not claimable (duplicate, cancelled or finished)", job_id)
        return
    job = SyncJob.objects.select_related("user").get(pk=job_id)
    SyncJob.objects.filter(pk=job_id).update(steps={"analysis": "running"})
    try:
        ProfileAnalysisService(job.user).run()
    except ProfileAnalysisError as exc:
        finish_job(
            job_id,
            Status.FAILED,
            steps={"analysis": "failed"},
            error_code=exc.code,
            error_detail=str(exc)[:500],
            completed_at=timezone.now(),
        )
        return
    finish_job(job_id, Status.COMPLETED, steps={"analysis": "done"}, completed_at=timezone.now())
