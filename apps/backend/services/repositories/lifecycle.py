"""Repository processing lifecycle (SRS-2 §23, design D5, job-claim-fencing D7).

DISCOVERED → FETCHING → ANALYZED → INDEXED → RECOMMENDABLE (or INDEXED when ineligible);
STALE → REFRESHING → RECOMMENDABLE/INDEXED; FAILED on a permanent GitHub error. Only one
analysis of a repository runs at a time: ``claim`` takes a row lock and refuses repositories
another worker is processing, unless that worker stopped renewing its claim (stale claim).

Each claim gets a token; only the analysis holding the current token can renew, release, fail
or complete the repository, so a reclaimed analysis changes nothing. ``claimed_at`` is the
claim's age; ``lifecycle_changed_at`` is the time of the last real transition, which a claim
and its release leave alone (the FAILED retry delay and the DISCOVERED grace period count
from it).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from django.db import transaction
from django.db.models import F, Q, QuerySet, Value
from django.db.models.functions import Coalesce, NullIf
from django.utils import timezone

from repositories.models import Lifecycle, Repository
from services.discovery.filters import REPOSITORY_UNAVAILABLE, FilterConfig, eligibility
from services.job_guard import stale_before

IN_PROGRESS = (Lifecycle.FETCHING, Lifecycle.REFRESHING)
# States whose stored data can be scored, together with ``is_eligible``: stale is not gone.
# Marking stale and claiming keep ``is_eligible``, so an eligible STALE or REFRESHING row was
# RECOMMENDABLE before; a FAILED retry (REFRESHING) stays ineligible.
SCORABLE = (Lifecycle.RECOMMENDABLE, Lifecycle.STALE, Lifecycle.REFRESHING)


class ClaimLost(Exception):
    """Another analysis reclaimed the repository: stop without writing."""


def abandoned_claims(now: datetime) -> Q:
    """In-progress repositories whose analysis stopped renewing its claim."""
    return Q(lifecycle__in=IN_PROGRESS) & (
        Q(claimed_at__lt=stale_before(now)) | Q(claimed_at__isnull=True)
    )


def _held(repo: Repository) -> QuerySet[Repository]:
    return Repository.objects.filter(
        pk=repo.pk, lifecycle__in=IN_PROGRESS, claim_token=repo.claim_token
    )


def claim(repo_id: int) -> Repository | None:
    """Move the repository to FETCHING (never analyzed) or REFRESHING under a new claim token,
    remembering the state to restore on a transient failure. Returns the locked-in repository
    (carrying the token), or None when it does not exist or another analysis is in progress.
    Stamped with the wall clock, never a job's reference time, so a long job's claims do not
    look stale to other workers."""
    now = timezone.now()
    with transaction.atomic():
        repo = Repository.objects.select_for_update().filter(pk=repo_id).first()
        if repo is None:
            return None
        if repo.lifecycle in IN_PROGRESS:
            if repo.claimed_at and repo.claimed_at >= stale_before(now):
                return None
            # Reclaiming a dead worker's claim: keep the state it saved before it started.
        else:
            repo.previous_lifecycle = repo.lifecycle
        repo.lifecycle = Lifecycle.FETCHING if repo.is_eligible is None else Lifecycle.REFRESHING
        repo.claim_token, repo.claimed_at = uuid.uuid4(), now
        repo.save(update_fields=["lifecycle", "previous_lifecycle", "claim_token", "claimed_at"])
    return repo


def renew(repo: Repository) -> None:
    """Keep a long analysis's claim fresh between the data types it fetches."""
    if not _held(repo).update(claimed_at=timezone.now()):
        raise ClaimLost()


def hold(repo: Repository) -> None:
    """Lock the repository inside the store transaction; raises ClaimLost (rolling back the
    transaction) when this analysis no longer holds the claim."""
    if not _held(repo).select_for_update().values_list("pk", flat=True).first():
        raise ClaimLost()


def release(repo: Repository) -> None:
    """Undo a claim after a transient failure or cancellation: restore the previous state, in
    one update, keeping that state's transition time. No-op when the claim was lost."""
    _held(repo).update(
        lifecycle=Coalesce(NullIf(F("previous_lifecycle"), Value("")), Value(Lifecycle.DISCOVERED)),
        previous_lifecycle="",
        claim_token=None,
        claimed_at=None,
    )


def fail(repo: Repository, code: str) -> None:
    """Permanent failure (not found, blocked): recorded as state, never as empty data."""
    _held(repo).update(
        lifecycle=Lifecycle.FAILED,
        lifecycle_error=code,
        previous_lifecycle="",
        stale_parts=[],
        is_eligible=False,
        ineligible_reason=REPOSITORY_UNAVAILABLE,
        lifecycle_changed_at=timezone.now(),
        claim_token=None,
        claimed_at=None,
        refresh_failed_at=None,  # the FAILED retry delay takes over
    )


def record_refresh_failure(repo_id: int, code: str, *, since: datetime) -> None:
    """A background refresh that started at ``since`` ended without a retry and without
    FAILED (stale is not gone): record why and when, keeping the state, eligibility and data.
    Called after the analysis released its claim, so a repository another analysis holds, one
    that changed state since (completed by another run), or a FAILED one is left alone."""
    Repository.objects.filter(pk=repo_id).exclude(
        lifecycle__in=(*IN_PROGRESS, Lifecycle.FAILED)
    ).exclude(lifecycle_changed_at__gte=since).update(
        lifecycle_error=code, refresh_failed_at=timezone.now()
    )


def complete(repo: Repository, *, now: datetime | None = None) -> None:
    """Finish the analysis as RECOMMENDABLE if eligible, else INDEXED (ANALYZED and INDEXED
    are passed through within the same transaction). Call after ``hold`` inside the
    transaction that stored the analyzed data."""
    now = now or timezone.now()
    reason = eligibility(repo, now=now, cfg=FilterConfig.from_settings())
    repo.is_eligible = reason is None
    repo.ineligible_reason = reason or ""
    repo.lifecycle = Lifecycle.RECOMMENDABLE if reason is None else Lifecycle.INDEXED
    repo.lifecycle_changed_at = timezone.now()
    repo.lifecycle_error = ""
    repo.previous_lifecycle = ""
    repo.stale_parts = []
    repo.claim_token, repo.claimed_at = None, None
    repo.refresh_failed_at = None
    repo.save(
        update_fields=[
            "lifecycle",
            "lifecycle_changed_at",
            "is_eligible",
            "ineligible_reason",
            "lifecycle_error",
            "previous_lifecycle",
            "stale_parts",
            "claim_token",
            "claimed_at",
            "refresh_failed_at",
        ]
    )
