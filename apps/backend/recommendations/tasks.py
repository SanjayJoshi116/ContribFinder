"""Recommendation generation and freshness (Phase 5). Thin wrappers around services."""

import logging
from typing import Any

from celery import shared_task

from jobs.models import SyncJob
from services.jobs import rerun_recommendations_if_requested, run_tracked_job
from services.ranking.freshness import start_due_generations
from services.ranking.service import RecommendationService

logger = logging.getLogger(__name__)


def _generate(job: SyncJob) -> None:
    RecommendationService(job).run()


@shared_task(
    bind=True, name="recommendations.generate_recommendations", acks_late=True, max_retries=None
)
def generate_recommendations(self: Any, job_id: int) -> None:
    """Run a recommendation generation job (job type ``recommendation_generation``)."""
    run_tracked_job(self, job_id, _generate, on_completed=rerun_recommendations_if_requested)


@shared_task(name="recommendations.refresh_recommendations")
def refresh_recommendations() -> int:
    """Beat: regenerate recommendations whose inputs changed since they were generated."""
    started = start_due_generations()
    if started:
        logger.info("Started %s recommendation generation job(s)", started)
    return started
