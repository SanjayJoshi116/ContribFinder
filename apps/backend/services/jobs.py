"""Starting, claiming, running, finishing and cancelling tracked jobs (design D5, Phase 3 D6,
Phase 4 D7)."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q, QuerySet
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import User
from github.models import GitHubAccount
from jobs.models import SyncJob
from services.errors import JobCancelled
from services.github.errors import GitHubError
from services.github.retry import Retry, decide_retry
from services.github.sync import STEPS, initial_steps

logger = logging.getLogger(__name__)

SYNC = SyncJob.JobType.GITHUB_PROFILE_SYNC
ANALYSIS = SyncJob.JobType.PROFILE_ANALYSIS
DISCOVERY = SyncJob.JobType.REPOSITORY_DISCOVERY
RECOMMENDATIONS = SyncJob.JobType.RECOMMENDATION_GENERATION
Status = SyncJob.Status

DISCOVERY_STEPS = ("queries", "search", "interactions", "analysis", "pool")
RECOMMENDATION_STEPS = ("recommendations",)
STEPS_BY_JOB_TYPE: dict[str, tuple[str, ...]] = {
    SYNC: STEPS,
    ANALYSIS: ("analysis",),
    DISCOVERY: DISCOVERY_STEPS,
    RECOMMENDATIONS: RECOMMENDATION_STEPS,
}


def claim_job(job_id: int) -> bool:
    """Atomically move a job to RUNNING. False for duplicate deliveries, cancelled or
    finished jobs. A RUNNING job that stopped updating (worker crash, redelivered task) is
    reclaimed."""
    now = timezone.now()
    stale_before = now - timedelta(seconds=settings.SYNC_STALE_AFTER_SECONDS)
    return bool(
        SyncJob.objects.filter(
            Q(status__in=[Status.PENDING, Status.RETRYING])
            | Q(status=Status.RUNNING, updated_at__lt=stale_before),
            pk=job_id,
        ).update(
            status=Status.RUNNING,
            attempts=F("attempts") + 1,
            started_at=Coalesce("started_at", now),
            updated_at=now,
        )
    )


def finish_job(job_id: int, status: str, **fields: Any) -> bool:
    """Move a RUNNING job to a terminal state (no-op if it was cancelled meanwhile)."""
    return bool(
        SyncJob.objects.filter(pk=job_id, status=Status.RUNNING).update(
            status=status, updated_at=timezone.now(), **fields
        )
    )


def _safe_detail(exc: Exception) -> str:
    # GitHubError messages are "GET <path> returned <status>" by construction; for anything
    # else keep only the type name so no unexpected content is stored.
    return str(exc)[:500] if isinstance(exc, GitHubError) else type(exc).__name__


def run_tracked_job(
    task: Any,
    job_id: int,
    runner: Callable[[SyncJob], None],
    *,
    on_completed: Callable[[SyncJob], None] | None = None,
) -> None:
    """Claim a job, run it, and translate failures through ``decide_retry`` into a Celery
    retry or a terminal FAILED state. ``on_completed`` runs once the job is COMPLETED; its
    errors are logged and never change the job's outcome."""
    if not claim_job(job_id):
        logger.info("Job %s not claimable (duplicate, cancelled or finished)", job_id)
        return
    job = SyncJob.objects.select_related("user").get(pk=job_id)

    try:
        runner(job)
    except JobCancelled:
        logger.info("Job %s cancelled", job_id)
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
                    "Job %s retrying in %ss after %s",
                    job_id,
                    decision.countdown,
                    type(exc).__name__,
                )
                raise task.retry(countdown=decision.countdown) from None
            return
        logger.warning("Job %s failed: %s (%s)", job_id, decision.code, type(exc).__name__)
        finish_job(
            job_id,
            Status.FAILED,
            error_code=decision.code,
            error_detail=_safe_detail(exc),
            completed_at=timezone.now(),
        )
        return

    completed = finish_job(
        job_id, Status.COMPLETED, error_code="", error_detail="", completed_at=timezone.now()
    )
    if completed and on_completed is not None:
        try:
            on_completed(job)
        except Exception:
            logger.exception("Follow-up of job %s failed", job_id)


class GitHubNotConnected(Exception):
    pass


@dataclass
class SyncCooldown(Exception):
    retry_after: int


def active_jobs(user: User, job_type: str = SYNC) -> QuerySet[SyncJob]:
    """Active jobs, excluding RUNNING jobs that stopped updating (dead worker)."""
    stale_before = timezone.now() - timedelta(seconds=settings.SYNC_STALE_AFTER_SECONDS)
    return SyncJob.objects.filter(user=user, job_type=job_type).filter(
        Q(status__in=[Status.PENDING, Status.RETRYING])
        | Q(status=Status.RUNNING, updated_at__gte=stale_before)
    )


def _task_for(job_type: str) -> Any:
    from developers.tasks import extract_developer_skills
    from github.tasks import sync_github_profile
    from recommendations.tasks import generate_recommendations
    from repositories.tasks import generate_candidates

    tasks: dict[str, Any] = {
        SYNC: sync_github_profile,
        ANALYSIS: extract_developer_skills,
        DISCOVERY: generate_candidates,
        RECOMMENDATIONS: generate_recommendations,
    }
    return tasks[job_type]


def recover_stale_jobs() -> dict[str, int]:
    """Requeue RUNNING jobs whose worker died (no heartbeat for ``SYNC_STALE_AFTER_SECONDS``),
    so they resume without waiting for the broker's visibility timeout. ``claim_job``
    reclaims them; a job that already used every attempt fails with ``worker_lost``."""
    now = timezone.now()
    stale = SyncJob.objects.filter(
        status=Status.RUNNING,
        updated_at__lt=now - timedelta(seconds=settings.SYNC_STALE_AFTER_SECONDS),
    )
    failed = stale.filter(attempts__gte=settings.SYNC_MAX_ATTEMPTS).update(
        status=Status.FAILED, error_code="worker_lost", completed_at=now, updated_at=now
    )
    requeued = 0
    for job_id, job_type in stale.values_list("pk", "job_type"):
        logger.warning("Job %s (%s) lost its worker; requeued", job_id, job_type)
        _task_for(job_type).delay(job_id)
        requeued += 1
    return {"requeued": requeued, "failed": failed}


def last_completed(user: User, job_type: str = SYNC) -> SyncJob | None:
    return (
        SyncJob.objects.filter(user=user, job_type=job_type, status=Status.COMPLETED)
        .order_by("-completed_at")
        .first()
    )


def _expire_stale(user: User, job_type: str = SYNC) -> None:
    stale_before = timezone.now() - timedelta(seconds=settings.SYNC_STALE_AFTER_SECONDS)
    SyncJob.objects.filter(
        user=user, job_type=job_type, status=Status.RUNNING, updated_at__lt=stale_before
    ).update(
        status=Status.FAILED,
        error_code="worker_lost",
        completed_at=timezone.now(),
        updated_at=timezone.now(),
    )


def start_profile_sync(user: User, *, enforce_cooldown: bool = True) -> tuple[SyncJob, bool]:
    """Return ``(job, created)``. An active job is returned as-is instead of starting another.

    Raises GitHubNotConnected, or SyncCooldown(retry_after) within the cooldown window.
    """
    from github.tasks import sync_github_profile  # avoid import cycle at module load

    if not GitHubAccount.objects.filter(user=user).exists():
        raise GitHubNotConnected()

    if existing := active_jobs(user).first():
        return existing, False

    if enforce_cooldown and (done := last_completed(user)) and done.completed_at:
        ready_at = done.completed_at + timedelta(seconds=settings.SYNC_COOLDOWN_SECONDS)
        remaining = (ready_at - timezone.now()).total_seconds()
        if remaining > 0:
            raise SyncCooldown(retry_after=math.ceil(remaining))

    _expire_stale(user)
    try:
        with transaction.atomic():
            job = SyncJob.objects.create(
                user=user, job_type=SYNC, status=Status.PENDING, steps=initial_steps()
            )
            transaction.on_commit(lambda: sync_github_profile.delay(job.pk))
    except IntegrityError:
        # A concurrent request created the active job first (partial unique constraint).
        return active_jobs(user).get(), False
    return job, True


def needs_initial_sync(user: User) -> bool:
    return last_completed(user) is None and not active_jobs(user).exists()


def start_profile_analysis(user: User) -> tuple[SyncJob, bool]:
    """Queue a standalone re-analysis of stored data (no GitHub calls). Returns the active
    analysis job instead of starting a second one."""
    from developers.tasks import extract_developer_skills  # avoid import cycle

    active = SyncJob.objects.filter(
        user=user, job_type=ANALYSIS, status__in=SyncJob.ACTIVE_STATUSES
    )
    if existing := active.first():
        return existing, False
    try:
        with transaction.atomic():
            job = SyncJob.objects.create(
                user=user, job_type=ANALYSIS, status=Status.PENDING, steps={"analysis": "pending"}
            )
            transaction.on_commit(lambda: extract_developer_skills.delay(job.pk))
    except IntegrityError:
        return active.get(), False
    return job, True


def cancel_active_syncs(user: User) -> int:
    return SyncJob.objects.filter(
        user=user, status__in=[Status.PENDING, Status.RUNNING, Status.RETRYING]
    ).update(status=Status.CANCELLED, completed_at=timezone.now(), updated_at=timezone.now())


def start_discovery(user: User) -> tuple[SyncJob | None, bool]:
    """Queue a repository discovery run (Phase 4). No job without an analyzed developer
    profile or a connected GitHub account; an active discovery is returned instead of a
    second one."""
    from developers.models import DeveloperProfile
    from repositories.tasks import generate_candidates  # avoid import cycle

    if not DeveloperProfile.objects.filter(user=user).exists():
        return None, False
    if not GitHubAccount.objects.filter(user=user).exists():
        return None, False
    if existing := active_jobs(user, DISCOVERY).first():
        return existing, False
    _expire_stale(user, DISCOVERY)
    try:
        with transaction.atomic():
            job = SyncJob.objects.create(
                user=user,
                job_type=DISCOVERY,
                status=Status.PENDING,
                steps=dict.fromkeys(DISCOVERY_STEPS, SyncJob.StepState.PENDING),
            )
            transaction.on_commit(lambda: generate_candidates.delay(job.pk))
    except IntegrityError:
        return active_jobs(user, DISCOVERY).first(), False
    return job, True


def start_discovery_after(job: SyncJob) -> None:
    """``on_completed`` hook of profile sync and profile analysis jobs."""
    start_discovery(job.user)


def start_recommendations(user: User) -> tuple[SyncJob | None, bool]:
    """Queue a recommendation generation (Phase 5). No job without a developer profile; an
    active generation is returned instead of a second one. Reads stored data only, so no
    GitHub account is needed."""
    from developers.models import DeveloperProfile
    from recommendations.tasks import generate_recommendations  # avoid import cycle

    if not DeveloperProfile.objects.filter(user=user).exists():
        return None, False
    if existing := active_jobs(user, RECOMMENDATIONS).first():
        return existing, False
    _expire_stale(user, RECOMMENDATIONS)
    try:
        with transaction.atomic():
            job = SyncJob.objects.create(
                user=user,
                job_type=RECOMMENDATIONS,
                status=Status.PENDING,
                steps=dict.fromkeys(RECOMMENDATION_STEPS, SyncJob.StepState.PENDING),
            )
            transaction.on_commit(lambda: generate_recommendations.delay(job.pk))
    except IntegrityError:
        return active_jobs(user, RECOMMENDATIONS).first(), False
    return job, True


def start_recommendations_after(job: SyncJob) -> None:
    """``on_completed`` hook of repository discovery jobs."""
    start_recommendations(job.user)
