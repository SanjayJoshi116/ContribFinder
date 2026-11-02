"""Background upkeep of shared candidate-repository data (design D8).

Repository work is not per user, so it is tracked by the repository lifecycle rather than a
SyncJob. Refreshes authenticate with the OAuth app's client credentials, never a user token.
Tasks take repository IDs only.
"""

import logging
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from jobs.models import SyncJob
from services.discovery.service import DiscoveryService
from services.github.client import GitHubClient
from services.github.errors import GitHubAuthError
from services.github.oauth import has_app_credentials
from services.github.retry import Retry, attempt_number, decide_retry
from services.jobs import run_tracked_job, start_recommendations_after
from services.repositories import backlog
from services.repositories.analysis import RepositoryAnalysisService
from services.repositories.lifecycle import record_refresh_failure

logger = logging.getLogger(__name__)


@shared_task(name="repositories.mark_stale_repositories")
def mark_stale_repositories() -> int:
    """Move pooled RECOMMENDABLE/INDEXED repositories with stale data types to STALE."""
    marked = backlog.mark_stale(timezone.now())
    logger.info("Marked %s repositories stale", marked)
    return marked


@shared_task(name="repositories.process_repository_backlog")
def process_repository_backlog() -> int:
    """Queue the refreshes ``services.repositories.backlog`` finds due."""
    if not has_app_credentials():
        logger.warning("GitHub client credentials are not configured; backlog not processed")
        return 0
    batch = backlog.queue_batch(timezone.now())
    refused: list[int] = []
    for repo_id, kind in batch:
        try:
            REFRESH_TASKS[kind].delay(repo_id)
        except Exception:
            logger.warning("Refresh of repository %s not queued", repo_id, exc_info=True)
            refused.append(repo_id)
    # Stamped by queue_batch, but no task will run: let the next run queue them again.
    backlog.unmark_queued(refused)
    logger.info("Queued %s repository refreshes", len(batch) - len(refused))
    return len(batch) - len(refused)


def _refresh(task: Any, repo_id: int, parts: list[str] | None) -> None:
    started = timezone.now()
    try:
        with GitHubClient.for_app() as client:
            outcome = RepositoryAnalysisService(client).run(repo_id, parts)
    except GitHubAuthError:
        logger.warning("Repository %s not refreshed: app credentials rejected", repo_id)
        record_refresh_failure(repo_id, backlog.AUTH_INVALID, since=started)
        return
    except Exception as exc:
        attempt = attempt_number(
            task.request.retries + 1,
            settings.SYNC_MAX_ATTEMPTS,
            eager=bool(task.request.is_eager),
        )
        decision = decide_retry(
            exc,
            attempt,
            max_attempts=settings.SYNC_MAX_ATTEMPTS,
            max_delay=settings.GITHUB_MAX_RETRY_DELAY,
        )
        if isinstance(decision, Retry):
            # Still queued until the retry has had its chance (backlog._not_queued).
            backlog.mark_queued([repo_id], timezone.now())
            raise task.retry(countdown=decision.countdown) from None
        # Not a GitHub failure (a bug, a database error): keep its traceback.
        unexpected = decision.code == "internal_error"
        logger.log(
            logging.ERROR if unexpected else logging.WARNING,
            "Repository %s refresh failed: %s",
            repo_id,
            decision.code,
            exc_info=unexpected,
        )
        record_refresh_failure(repo_id, decision.code, since=started)
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


@shared_task(
    bind=True, name="repositories.sync_repository_issues", acks_late=True, max_retries=None
)
def sync_repository_issues(self: Any, repo_id: int) -> None:
    """Refresh only a repository's open issues (their staleness age is the shortest)."""
    _refresh(self, repo_id, ["issues"])


REFRESH_TASKS = {
    "all": sync_repository,
    "readme": sync_repository_readme,
    "issues": sync_repository_issues,
}


__all__ = [
    "generate_candidates",
    "mark_stale_repositories",
    "process_repository_backlog",
    "sync_repository",
    "sync_repository_issues",
    "sync_repository_readme",
]


def _discover(job: SyncJob) -> None:
    DiscoveryService(job).run()


@shared_task(bind=True, name="repositories.generate_candidates", acks_late=True, max_retries=None)
def generate_candidates(self: Any, job_id: int) -> None:
    """Run a repository discovery job (job type ``repository_discovery``). Job ID only."""
    run_tracked_job(self, job_id, _discover, on_completed=start_recommendations_after)
