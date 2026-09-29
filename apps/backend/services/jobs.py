"""Starting, claiming, finishing and cancelling tracked jobs (design D5, Phase 3 D6)."""

from __future__ import annotations

import math
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
from services.github.sync import STEPS, initial_steps

SYNC = SyncJob.JobType.GITHUB_PROFILE_SYNC
ANALYSIS = SyncJob.JobType.PROFILE_ANALYSIS
Status = SyncJob.Status

STEPS_BY_JOB_TYPE: dict[str, tuple[str, ...]] = {SYNC: STEPS, ANALYSIS: ("analysis",)}


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


def finish_job(job_id: int, status: str, **fields: Any) -> None:
    """Move a RUNNING job to a terminal state (no-op if it was cancelled meanwhile)."""
    SyncJob.objects.filter(pk=job_id, status=Status.RUNNING).update(
        status=status, updated_at=timezone.now(), **fields
    )


class GitHubNotConnected(Exception):
    pass


@dataclass
class SyncCooldown(Exception):
    retry_after: int


def active_jobs(user: User) -> QuerySet[SyncJob]:
    """Active jobs, excluding RUNNING jobs that stopped updating (dead worker)."""
    stale_before = timezone.now() - timedelta(seconds=settings.SYNC_STALE_AFTER_SECONDS)
    return SyncJob.objects.filter(user=user, job_type=SYNC).filter(
        Q(status__in=[Status.PENDING, Status.RETRYING])
        | Q(status=Status.RUNNING, updated_at__gte=stale_before)
    )


def last_completed(user: User) -> SyncJob | None:
    return (
        SyncJob.objects.filter(user=user, job_type=SYNC, status=Status.COMPLETED)
        .order_by("-completed_at")
        .first()
    )


def _expire_stale(user: User) -> None:
    stale_before = timezone.now() - timedelta(seconds=settings.SYNC_STALE_AFTER_SECONDS)
    SyncJob.objects.filter(
        user=user, job_type=SYNC, status=Status.RUNNING, updated_at__lt=stale_before
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
