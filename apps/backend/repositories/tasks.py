"""Background upkeep of shared candidate-repository data (design D8).

Repository work is not per user, so it is tracked by the repository lifecycle rather than a
SyncJob. Refreshes authenticate with the OAuth app's client credentials, never a user token.
Tasks take repository IDs only.
"""

import logging
from datetime import timedelta
from typing import Any

from celery import shared_task
from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone

from jobs.models import SyncJob
from repositories.models import Lifecycle, Repository
from services.discovery.service import DiscoveryService
from services.github.client import GitHubClient
from services.github.errors import GitHubAuthError
from services.github.retry import Retry, decide_retry
from services.jobs import run_tracked_job, start_recommendations_after
from services.repositories.analysis import RepositoryAnalysisService
from services.repositories.lifecycle import IN_PROGRESS
from services.repositories.staleness import stale_parts

logger = logging.getLogger(__name__)


def _pooled() -> Any:
    """Repositories in at least one developer's candidate pool."""
    return Repository.objects.filter(candidates__isnull=False).distinct()


def _has_app_credentials() -> bool:
    return bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET)


@shared_task(name="repositories.mark_stale_repositories")
def mark_stale_repositories() -> int:
    """Move pooled RECOMMENDABLE/INDEXED repositories with stale data types to STALE."""
    now = timezone.now()
    marked = 0
    candidates = _pooled().filter(lifecycle__in=[Lifecycle.RECOMMENDABLE, Lifecycle.INDEXED])
    for repo in candidates.order_by("pk").iterator(chunk_size=500):
        parts = stale_parts(repo, now)
        if not parts:
            continue
        marked += Repository.objects.filter(pk=repo.pk, lifecycle=repo.lifecycle).update(
            lifecycle=Lifecycle.STALE,
            previous_lifecycle=repo.lifecycle,
            stale_parts=parts,
            lifecycle_changed_at=now,
        )
    logger.info("Marked %s repositories stale", marked)
    return marked


@shared_task(name="repositories.process_repository_backlog")
def process_repository_backlog() -> int:
    """Queue refreshes for pooled repositories that are stale, still unanalyzed after the
    grace period, failed and due for a retry, or left mid-analysis by a dead worker."""
    if not _has_app_credentials():
        logger.warning("GitHub client credentials are not configured; backlog not processed")
        return 0
    now = timezone.now()
    grace = now - timedelta(minutes=settings.REPO_DISCOVERED_GRACE_MINUTES)
    retry = now - timedelta(hours=settings.REPO_FAILED_RETRY_HOURS)
    abandoned = now - timedelta(seconds=settings.SYNC_STALE_AFTER_SECONDS)
    due = (
        Q(lifecycle=Lifecycle.STALE)
        | Q(lifecycle=Lifecycle.DISCOVERED)
        & (Q(lifecycle_changed_at__lt=grace) | Q(lifecycle_changed_at__isnull=True))
        | Q(lifecycle=Lifecycle.FAILED, lifecycle_changed_at__lt=retry)
        | Q(lifecycle__in=IN_PROGRESS, lifecycle_changed_at__lt=abandoned)
    )
    batch = list(
        _pooled()
        .filter(due)
        .order_by(F("lifecycle_changed_at").asc(nulls_first=True), "pk")
        .values_list("pk", "stale_parts")[: settings.REPO_REFRESH_BATCH]
    )
    for repo_id, parts in batch:
        if parts == ["readme"]:
            sync_repository_readme.delay(repo_id)
        else:
            sync_repository.delay(repo_id)
    logger.info("Queued %s repository refreshes", len(batch))
    return len(batch)


def _refresh(task: Any, repo_id: int, parts: list[str] | None) -> None:
    try:
        with GitHubClient.for_app() as client:
            outcome = RepositoryAnalysisService(client).run(repo_id, parts)
    except GitHubAuthError:
        logger.warning("Repository %s not refreshed: app credentials rejected", repo_id)
        return
    except Exception as exc:
        decision = decide_retry(
            exc,
            task.request.retries + 1,
            max_attempts=settings.SYNC_MAX_ATTEMPTS,
            max_delay=settings.GITHUB_MAX_RETRY_DELAY,
        )
        if isinstance(decision, Retry):
            raise task.retry(countdown=decision.countdown) from None
        logger.warning("Repository %s refresh failed: %s", repo_id, decision.code)
        return
    logger.info("Repository %s refresh: %s", repo_id, outcome)


@shared_task(bind=True, name="repositories.sync_repository", acks_late=True, max_retries=None)
def sync_repository(self: Any, repo_id: int) -> None:
    """Refresh a repository's stale (or, never analyzed, all) data types."""
    _refresh(self, repo_id, None)


@shared_task(
    bind=True, name="repositories.sync_repository_readme", acks_late=True, max_retries=None
)
def sync_repository_readme(self: Any, repo_id: int) -> None:
    _refresh(self, repo_id, ["readme"])


__all__ = [
    "generate_candidates",
    "mark_stale_repositories",
    "process_repository_backlog",
    "stale_parts",
    "sync_repository",
    "sync_repository_readme",
]


def _discover(job: SyncJob) -> None:
    DiscoveryService(job).run()


@shared_task(bind=True, name="repositories.generate_candidates", acks_late=True, max_retries=None)
def generate_candidates(self: Any, job_id: int) -> None:
    """Run a repository discovery job (job type ``repository_discovery``). Job ID only."""
    run_tracked_job(self, job_id, _discover, on_completed=start_recommendations_after)
