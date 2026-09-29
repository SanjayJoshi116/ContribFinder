from typing import Any

from celery import shared_task

from jobs.models import SyncJob
from services.github.sync import GitHubSyncService
from services.jobs import claim_job, run_tracked_job, start_discovery_after

__all__ = ["claim_job", "sync_github_profile"]


def _run(job: SyncJob) -> None:
    GitHubSyncService(job).run()


@shared_task(bind=True, name="github.sync_github_profile", acks_late=True, max_retries=None)
def sync_github_profile(self: Any, job_id: int) -> None:
    """Run a GitHub profile sync job. Takes only the job ID; never a credential. A completed
    sync starts repository discovery (Phase 4)."""
    run_tracked_job(self, job_id, _run, on_completed=start_discovery_after)
