"""Starting, claiming, running, finishing and cancelling tracked jobs (design D5, Phase 3 D6,
Phase 4 D7, job-claim-fencing D1-D5)."""

from __future__ import annotations

import logging
import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q, QuerySet
from django.db.models.functions import Coalesce
from django.utils import timezone
from kombu.exceptions import OperationalError as BrokerError

from accounts.models import User
from github.models import GitHubAccount
from jobs.models import SyncJob
from services.errors import JobCancelled, PermanentJobError
from services.github.errors import GitHubError
from services.github.retry import Retry, attempt_number, decide_retry
from services.github.sync import STEPS
from services.job_guard import held, lost_before, stale_before

logger = logging.getLogger(__name__)

SYNC = SyncJob.JobType.GITHUB_PROFILE_SYNC
ANALYSIS = SyncJob.JobType.PROFILE_ANALYSIS
DISCOVERY = SyncJob.JobType.REPOSITORY_DISCOVERY
RECOMMENDATIONS = SyncJob.JobType.RECOMMENDATION_GENERATION
Status = SyncJob.Status

DISCOVERY_STEPS = ("queries", "search", "interactions", "pool", "analysis")
RECOMMENDATION_STEPS = ("recommendations",)
STEPS_BY_JOB_TYPE: dict[str, tuple[str, ...]] = {
    SYNC: STEPS,
    ANALYSIS: ("analysis",),
    DISCOVERY: DISCOVERY_STEPS,
    RECOMMENDATIONS: RECOMMENDATION_STEPS,
}


def _stale_running(now: datetime) -> Q:
    """RUNNING jobs that stopped sending heartbeats: their worker died (or is too slow). The
    query form of ``job_guard.is_stalled``."""
    return Q(status=Status.RUNNING, updated_at__lt=stale_before(now))


def claim_job(job_id: int) -> SyncJob | None:
    """Atomically move a job to RUNNING under a new claim token and return it. None for
    duplicate deliveries, cancelled or finished jobs. A RUNNING job that stopped updating
    (worker crash, redelivered task) is reclaimed, which fences out its previous worker. A job
    that already used every attempt ends as FAILED ``worker_lost`` instead of running again."""
    now = timezone.now()
    claimable = SyncJob.objects.filter(
        Q(status__in=[Status.PENDING, Status.RETRYING]) | _stale_running(now), pk=job_id
    )
    token = uuid.uuid4()
    claimed = claimable.filter(attempts__lt=settings.SYNC_MAX_ATTEMPTS).update(
        status=Status.RUNNING,
        claim_token=token,
        rerun_requested=False,  # this attempt loads its inputs: an earlier request is covered
        attempts=F("attempts") + 1,
        started_at=Coalesce("started_at", now),
        updated_at=now,
    )
    if not claimed:
        if _end_jobs(claimable, Status.FAILED, error_code="worker_lost"):
            logger.warning("Job %s used every attempt; failed", job_id)
        return None
    job = SyncJob.objects.select_related("user").filter(pk=job_id).first()
    if job is None:  # deleted with the user's data right after the claim
        return None
    job.claim_token = token
    return job


def _end_jobs(jobs: QuerySet[SyncJob], status: str, **fields: Any) -> int:
    """End matching jobs as ``status`` (a terminal state): revoke the claim and turn every
    ``running`` step into ``failed``, so no finished job shows work in progress (D3)."""
    now = timezone.now()
    fields = {"completed_at": now, **fields}
    ended = 0
    with transaction.atomic():
        # One lock order for every caller (recovery, cancel, expiry), so they never deadlock.
        for job in jobs.order_by("pk").select_for_update():
            job.steps = {
                name: SyncJob.StepState.FAILED if state == SyncJob.StepState.RUNNING else state
                for name, state in (job.steps or {}).items()
            }
            job.status, job.claim_token, job.updated_at = status, None, now
            for name, value in fields.items():
                setattr(job, name, value)
            job.save(update_fields=["steps", "status", "claim_token", "updated_at", *fields])
            ended += 1
    return ended


def finish_job(job: SyncJob, status: str, **fields: Any) -> bool:
    """Move a RUNNING job to a terminal state. False (no-op) if it was cancelled meanwhile or
    another worker holds its claim now."""
    return bool(_end_jobs(held(job), status, **fields))


def _safe_detail(exc: Exception) -> str:
    # GitHubError messages are "GET <path> returned <status>" by construction, and
    # PermanentJobError messages are built by our code; for anything else keep only the type
    # name so no unexpected content is stored.
    if isinstance(exc, GitHubError | PermanentJobError):
        return str(exc)[:500]
    return type(exc).__name__


def run_tracked_job(
    task: Any,
    job_id: int,
    runner: Callable[[SyncJob], None],
    *,
    on_completed: Callable[[SyncJob], None] | None = None,
    on_failed: Callable[[SyncJob], None] | None = None,
) -> None:
    """Claim a job, run it, and translate failures through ``decide_retry`` into a Celery
    retry or a terminal FAILED state. ``on_completed`` runs once the job is COMPLETED,
    ``on_failed`` once it is FAILED for good (never on a scheduled retry or a cancel); their
    errors are logged and never change the job's outcome. The hook runs in the transaction that
    ends the job, so the follow-up job it starts is committed with the outcome: a status read
    never sees the job finished without its follow-up (PIPE-1). Its tasks are sent on commit.

    Without a worker (eager mode) nothing is retried inline: a retryable error fails the job
    with the code it would get after its last attempt (D4)."""
    job = claim_job(job_id)
    if job is None:
        logger.info("Job %s not claimable (duplicate, cancelled or finished)", job_id)
        return

    try:
        runner(job)
    except JobCancelled:
        logger.info("Job %s cancelled or reclaimed", job_id)
        return
    except Exception as exc:
        decision = decide_retry(
            exc,
            attempt_number(
                job.attempts, settings.SYNC_MAX_ATTEMPTS, eager=settings.CELERY_TASK_ALWAYS_EAGER
            ),
            max_attempts=settings.SYNC_MAX_ATTEMPTS,
            max_delay=settings.GITHUB_MAX_RETRY_DELAY,
        )
        if isinstance(decision, Retry):
            moved = held(job).update(
                status=Status.RETRYING,
                claim_token=None,
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
        _finish_and_follow_up(
            job,
            Status.FAILED,
            on_failed,
            error_code=decision.code,
            error_detail=_safe_detail(exc),
            completed_at=timezone.now(),
        )
        return

    _finish_and_follow_up(
        job,
        Status.COMPLETED,
        on_completed,
        error_code="",
        error_detail="",
        completed_at=timezone.now(),
    )


def _finish_and_follow_up(
    job: SyncJob, status: str, hook: Callable[[SyncJob], None] | None, **fields: Any
) -> None:
    """End the job and run its hook in one transaction (job lock first, as `services/locks.py`).

    With a hook, every active job of the user is locked first, in pk order, as ``_end_jobs``
    does: the hook may expire the user's stale jobs (``_expire_stale``), and taking those locks
    after the finishing job's own would deadlock with recovery or a cancel.

    The hook's tasks are sent on commit, outside its savepoint: any error from sending (a broker
    that refuses it) or from running one inline (eager mode) is logged, as a failing hook is.
    The job is ended, and job recovery re-sends a PENDING follow-up."""
    committed = False

    def mark_committed() -> None:
        nonlocal committed
        committed = True

    try:
        with transaction.atomic():
            transaction.on_commit(mark_committed)  # runs before the hook's callbacks
            if hook is not None:
                list(
                    SyncJob.objects.filter(user_id=job.user_id, status__in=SyncJob.ACTIVE_STATUSES)
                    .order_by("pk")
                    .select_for_update()
                    .values_list("pk", flat=True)
                )
            if finish_job(job, status, **fields):
                _follow_up(hook, job)
    except Exception as exc:
        if not committed:
            raise
        if isinstance(exc, BrokerError):
            logger.exception("Follow-up task of job %s not queued", job.pk)
        else:
            logger.exception("Follow-up of job %s failed", job.pk)


def _follow_up(hook: Callable[[SyncJob], None] | None, job: SyncJob) -> None:
    """Run ``hook`` in a savepoint: a failing hook rolls back only its own writes."""
    if hook is None:
        return
    try:
        with transaction.atomic():
            hook(job)
    except Exception:
        logger.exception("Follow-up of job %s failed", job.pk)


class GitHubNotConnected(Exception):
    pass


@dataclass
class SyncCooldown(Exception):
    retry_after: int


def active_jobs(user: User, job_type: str = SYNC) -> QuerySet[SyncJob]:
    """Active jobs, excluding RUNNING jobs that stopped updating (dead worker)."""
    return SyncJob.objects.filter(
        user=user, job_type=job_type, status__in=SyncJob.ACTIVE_STATUSES
    ).exclude(_stale_running(timezone.now()))


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
    """Requeue jobs that lost their worker or their queued task (D2).

    - RUNNING with no heartbeat for ``SYNC_STALE_AFTER_SECONDS``: the worker died. The job moves
      to RETRYING with its claim revoked (fencing out a worker that is only slow) and is
      requeued once, without waiting for the broker's visibility timeout. A job that already
      used every attempt fails with ``worker_lost``.
    - PENDING or RETRYING untouched for ``SYNC_STALE_AFTER_SECONDS + GITHUB_MAX_RETRY_DELAY``:
      its message was lost. It is requeued, and ``updated_at`` is bumped so the next run waits
      a full period again. ``claim_job`` lets only one delivery run a duplicate."""
    now = timezone.now()
    stale = SyncJob.objects.filter(_stale_running(now))
    failed = _end_jobs(
        stale.filter(attempts__gte=settings.SYNC_MAX_ATTEMPTS),
        Status.FAILED,
        error_code="worker_lost",
    )
    waiting = SyncJob.objects.filter(
        status__in=[Status.PENDING, Status.RETRYING], updated_at__lt=lost_before(now)
    )
    # Stale jobs first: once RETRYING with updated_at = now, they are no longer "waiting".
    requeued = _requeue(
        stale, "lost its worker", status=Status.RETRYING, claim_token=None, updated_at=now
    )
    requeued += _requeue(waiting, "was never picked up", updated_at=now)
    return {"requeued": requeued, "failed": failed}


def _requeue(jobs: QuerySet[SyncJob], reason: str, **update: Any) -> int:
    """Apply ``update`` to each job still matching ``jobs`` and send its task once."""
    requeued = 0
    for job_id, job_type in list(jobs.values_list("pk", "job_type")):
        if jobs.filter(pk=job_id).update(**update):
            logger.warning("Job %s (%s) %s; requeued", job_id, job_type, reason)
            _task_for(job_type).delay(job_id)
            requeued += 1
    return requeued


def last_completed(user: User, job_type: str = SYNC) -> SyncJob | None:
    return (
        SyncJob.objects.filter(user=user, job_type=job_type, status=Status.COMPLETED)
        .order_by("-completed_at")
        .first()
    )


def _expire_stale(user: User, job_type: str = SYNC) -> None:
    _end_jobs(
        SyncJob.objects.filter(_stale_running(timezone.now()), user=user, job_type=job_type),
        Status.FAILED,
        error_code="worker_lost",
    )


def new_job(user: User, job_type: str) -> SyncJob:
    """A PENDING job of ``job_type`` with every step pending. Nothing is queued and nothing is
    checked: a second active job of a type fails the partial unique constraint. Real jobs start
    through ``start_*`` (``_start_job``), which handles both."""
    return SyncJob.objects.create(
        user=user,
        job_type=job_type,
        status=Status.PENDING,
        steps=dict.fromkeys(STEPS_BY_JOB_TYPE[job_type], SyncJob.StepState.PENDING),
    )


def _start_job(user: User, job_type: str) -> tuple[SyncJob, bool]:
    """Return ``(job, created)``: the active job of this type, or a new one queued on commit.
    A RUNNING job that stopped updating is not active: it fails with ``worker_lost`` (D5)."""
    if existing := active_jobs(user, job_type).first():
        return existing, False
    _expire_stale(user, job_type)
    task = _task_for(job_type)
    try:
        with transaction.atomic():
            job = new_job(user, job_type)
            transaction.on_commit(lambda: task.delay(job.pk))
    except IntegrityError:
        # A concurrent start created the active job first (partial unique constraint). It may
        # have finished since: then report that job as it is now, never a server error.
        conflicting = (
            active_jobs(user, job_type).first()
            or SyncJob.objects.filter(user=user, job_type=job_type).order_by("-created_at").first()
        )
        if conflicting is None:
            raise
        return conflicting, False
    return job, True


def start_profile_sync(user: User, *, enforce_cooldown: bool = True) -> tuple[SyncJob, bool]:
    """Return ``(job, created)``. An active job is returned as-is instead of starting another.

    Raises GitHubNotConnected, or SyncCooldown(retry_after) within the cooldown window.
    """
    if not GitHubAccount.objects.filter(user=user).exists():
        raise GitHubNotConnected()

    if existing := active_jobs(user).first():
        return existing, False

    if enforce_cooldown and (done := last_completed(user)) and done.completed_at:
        ready_at = done.completed_at + timedelta(seconds=settings.SYNC_COOLDOWN_SECONDS)
        remaining = (ready_at - timezone.now()).total_seconds()
        if remaining > 0:
            raise SyncCooldown(retry_after=math.ceil(remaining))

    return _start_job(user, SYNC)


def needs_initial_sync(user: User) -> bool:
    return last_completed(user) is None and not active_jobs(user).exists()


def start_profile_analysis(user: User) -> tuple[SyncJob, bool]:
    """Queue a standalone re-analysis of stored data (no GitHub calls). Returns the active
    analysis job instead of starting a second one."""
    return _start_job(user, ANALYSIS)


def cancel_active_syncs(user: User) -> int:
    return _end_jobs(
        SyncJob.objects.filter(user=user, status__in=SyncJob.ACTIVE_STATUSES), Status.CANCELLED
    )


def start_discovery(user: User) -> tuple[SyncJob | None, bool]:
    """Queue a repository discovery run (Phase 4). No job without an analyzed developer
    profile or a connected GitHub account; an active discovery is returned instead of a
    second one."""
    from developers.models import DeveloperProfile

    if not DeveloperProfile.objects.filter(user=user).exists():
        return None, False
    if not GitHubAccount.objects.filter(user=user).exists():
        return None, False
    return _start_job(user, DISCOVERY)


def start_discovery_after(job: SyncJob) -> None:
    """``on_completed`` hook of profile sync and profile analysis jobs."""
    start_discovery(job.user)


def start_recommendations(
    user: User, *, rerun_if_running: bool = True
) -> tuple[SyncJob | None, bool]:
    """Queue a recommendation generation (Phase 5). No job without a developer profile; an
    active generation is returned instead of a second one, and a running one is asked to run
    again unless ``rerun_if_running`` is false. Reads stored data only, so no GitHub account
    is needed."""
    from developers.models import DeveloperProfile

    if not DeveloperProfile.objects.filter(user=user).exists():
        return None, False
    job, created = _start_job(user, RECOMMENDATIONS)
    if created or job.status != Status.RUNNING or not rerun_if_running:
        return job, created  # a pending or retrying job loads its inputs when it runs
    # A running job may have loaded its inputs already: have it run again once it completes.
    # Serialized with its completion on the job row; if it finished first, start a new one.
    if SyncJob.objects.filter(pk=job.pk, status=Status.RUNNING).update(rerun_requested=True):
        return job, False
    return _start_job(user, RECOMMENDATIONS)


def rerun_recommendations_if_requested(job: SyncJob) -> None:
    """``on_completed`` and ``on_failed`` hook of recommendation generation jobs (see
    ``start_recommendations``): a request made while the job ran is never lost."""
    if SyncJob.objects.filter(pk=job.pk, rerun_requested=True).exists():
        start_recommendations(job.user)


def start_recommendations_after(job: SyncJob) -> None:
    """``on_completed`` hook of repository discovery jobs."""
    start_recommendations(job.user)
