"""Repository processing lifecycle (SRS-2 §23, design D5).

DISCOVERED → FETCHING → ANALYZED → INDEXED → RECOMMENDABLE (or INDEXED when ineligible);
STALE → REFRESHING → RECOMMENDABLE/INDEXED; FAILED on a permanent GitHub error. Only one
analysis of a repository runs at a time: ``claim`` takes a row lock and refuses repositories
another worker is processing, unless that worker stopped updating (stale claim).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from repositories.models import Lifecycle, Repository
from services.discovery.filters import REPOSITORY_UNAVAILABLE, FilterConfig, eligibility

IN_PROGRESS = (Lifecycle.FETCHING, Lifecycle.REFRESHING)


def claim(repo_id: int) -> Repository | None:
    """Move the repository to FETCHING (never analyzed) or REFRESHING, remembering the state
    to restore on a transient failure. Returns the locked-in repository, or None when it does
    not exist or another analysis is in progress. Stamped with the wall clock, never a job's
    reference time, so a long job's claims do not look stale to other workers."""
    now = timezone.now()
    stale_before = now - timedelta(seconds=settings.SYNC_STALE_AFTER_SECONDS)
    with transaction.atomic():
        repo = Repository.objects.select_for_update().filter(pk=repo_id).first()
        if repo is None:
            return None
        if repo.lifecycle in IN_PROGRESS:
            if repo.lifecycle_changed_at and repo.lifecycle_changed_at >= stale_before:
                return None
            # Reclaiming a dead worker's claim: keep the state it saved before it started.
        else:
            repo.previous_lifecycle = repo.lifecycle
        repo.lifecycle = Lifecycle.FETCHING if repo.is_eligible is None else Lifecycle.REFRESHING
        repo.lifecycle_changed_at = now
        repo.save(update_fields=["lifecycle", "previous_lifecycle", "lifecycle_changed_at"])
    return repo


def release(repo_id: int) -> None:
    """Undo a claim after a transient failure or cancellation: restore the previous state."""
    repo = Repository.objects.filter(pk=repo_id, lifecycle__in=IN_PROGRESS).first()
    if repo is None:
        return
    Repository.objects.filter(pk=repo_id, lifecycle__in=IN_PROGRESS).update(
        lifecycle=repo.previous_lifecycle or Lifecycle.DISCOVERED,
        previous_lifecycle="",
        lifecycle_changed_at=timezone.now(),
    )


def fail(repo_id: int, code: str) -> None:
    """Permanent failure (not found, blocked): recorded as state, never as empty data."""
    Repository.objects.filter(pk=repo_id).update(
        lifecycle=Lifecycle.FAILED,
        lifecycle_error=code,
        previous_lifecycle="",
        stale_parts=[],
        is_eligible=False,
        ineligible_reason=REPOSITORY_UNAVAILABLE,
        lifecycle_changed_at=timezone.now(),
    )


def complete(repo: Repository, *, now: datetime | None = None) -> None:
    """Walk ANALYZED → INDEXED, then RECOMMENDABLE if eligible. Call inside the transaction
    that stored the analyzed data."""
    now = now or timezone.now()
    fields = ["lifecycle", "lifecycle_changed_at"]
    for state in (Lifecycle.ANALYZED, Lifecycle.INDEXED):
        repo.lifecycle, repo.lifecycle_changed_at = state, timezone.now()
        repo.save(update_fields=fields)
    reason = eligibility(repo, now=now, cfg=FilterConfig.from_settings())
    repo.is_eligible = reason is None
    repo.ineligible_reason = reason or ""
    repo.lifecycle = Lifecycle.RECOMMENDABLE if reason is None else Lifecycle.INDEXED
    repo.lifecycle_error = ""
    repo.previous_lifecycle = ""
    repo.stale_parts = []
    repo.save(
        update_fields=[
            *fields,
            "is_eligible",
            "ineligible_reason",
            "lifecycle_error",
            "previous_lifecycle",
            "stale_parts",
        ]
    )
