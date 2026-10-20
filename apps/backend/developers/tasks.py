from typing import Any

from celery import shared_task

from jobs.models import SyncJob
from services.job_guard import save_progress
from services.jobs import run_tracked_job, start_discovery_after
from services.profiling.analysis import ProfileAnalysisService

Step = SyncJob.StepState


def _analyze(job: SyncJob) -> None:
    save_progress(job, steps={"analysis": Step.RUNNING})
    ProfileAnalysisService(job.user, job=job).run()
    save_progress(job, steps={"analysis": Step.DONE})


@shared_task(bind=True, name="developers.extract_developer_skills", acks_late=True)
def extract_developer_skills(self: Any, job_id: int) -> None:
    """Re-analyze a user's profile from stored data (job type ``profile_analysis``).

    Analysis is deterministic and makes no GitHub requests, so failures are not retried:
    ``ProfileAnalysisError`` fails the job with ``analysis_failed`` and the previous profile
    stays in place."""
    run_tracked_job(self, job_id, _analyze, on_completed=start_discovery_after)
