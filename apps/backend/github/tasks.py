from typing import Any

from celery import shared_task

from jobs.models import SyncJob
from services.github.accounts import revoke_replaced
from services.github.sync import GitHubSyncService
from services.jobs import claim_job, run_tracked_job, start_discovery_after

__all__ = ["claim_job", "revoke_replaced_token", "sync_github_profile"]


def _run(job: SyncJob) -> None:
    GitHubSyncService(job).run()


@shared_task(bind=True, name="github.sync_github_profile", acks_late=True, max_retries=None)
def sync_github_profile(self: Any, job_id: int) -> None:
    """Run a GitHub profile sync job. Takes only the job ID; never a credential. A completed
    sync starts repository discovery (Phase 4)."""
    run_tracked_job(self, job_id, _run, on_completed=start_discovery_after)


@shared_task(name="github.revoke_replaced_token", acks_late=True)
def revoke_replaced_token(github_id: int, previous_encrypted: str) -> None:
    """Revoke the token a sign-in replaced. Takes the old token encrypted only: it is useless
    without the server's keys. Best effort, never retried."""
    revoke_replaced(github_id, previous_encrypted)
