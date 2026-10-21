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

This module is the only writer of eligibility and of the RECOMMENDABLE / INDEXED state.
Repository rows locked in bulk are locked in GitHub ID order.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime

from django.db import transaction
from django.db.models import CharField, F, Q, QuerySet, Value
from django.db.models.functions import Coalesce, Concat, NullIf
from django.utils import timezone

from repositories.models import Lifecycle, Repository
from services.discovery.filters import (
    NAME_RELEASED,
    REPOSITORY_UNAVAILABLE,
    FilterConfig,
    eligibility,
    has_dependencies_annotation,
)
from services.job_guard import stale_before

from .staleness import RELEASED_MARK

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


def hold(repo: Repository, *, fetched_name: str | None = None) -> None:
    """Lock the repository inside the store transaction and refresh ``repo`` from the locked
    row, so eligibility sees what searches stored meanwhile. Raises ClaimLost (rolling back
    the transaction) when this analysis no longer holds the claim, or when the data was
    fetched under ``fetched_name`` (no metadata fetched) and the name changed since: the
    fetched data may belong to another repository."""
    try:
        repo.refresh_from_db(from_queryset=_held(repo).select_for_update())
    except Repository.DoesNotExist:
        raise ClaimLost() from None
    if fetched_name is not None and repo.full_name != fetched_name:
        raise ClaimLost()


def release_name(full_name: str, github_id: int) -> None:
    """Free ``full_name`` for ``github_id``: another row holding it (renamed away on GitHub,
    or deleted and recreated) becomes ``{full_name}~{its github_id}`` and keeps its data and
    links. Its stale metadata (staleness.is_released_name) makes the next analysis look it up
    by GitHub ID. Until then its name and URL are wrong, so an eligible holder becomes
    ineligible (``name_released``) and INDEXED; that analysis decides eligibility again."""
    holders = list(
        Repository.objects.filter(full_name=full_name)
        .exclude(github_id=github_id)
        .values_list("pk", flat=True)
    )
    if not holders:
        return
    rows = Repository.objects.filter(pk__in=holders)
    rows.update(
        full_name=Concat(
            F("full_name"), Value(RELEASED_MARK), F("github_id"), output_field=CharField()
        )
    )
    rows.filter(is_eligible=True).update(is_eligible=False, ineligible_reason=NAME_RELEASED)
    rows.filter(lifecycle=Lifecycle.RECOMMENDABLE).update(
        lifecycle=Lifecycle.INDEXED, lifecycle_changed_at=timezone.now()
    )
    # A claimed holder restores INDEXED, not RECOMMENDABLE, if its analysis is released.
    rows.filter(previous_lifecycle=Lifecycle.RECOMMENDABLE).update(
        previous_lifecycle=Lifecycle.INDEXED
    )


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
        refresh_queued_at=None,
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
    repo.refresh_queued_at = None
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
            "refresh_queued_at",
        ]
    )


# Settled states whose eligibility a re-check may change: in-progress rows are decided by
# their analysis, FAILED rows keep their failure, DISCOVERED rows have no eligibility yet.
RECHECKABLE = (Lifecycle.RECOMMENDABLE, Lifecycle.INDEXED, Lifecycle.STALE)


def recheck_eligibility(repo_ids: Iterable[int], *, now: datetime) -> int:
    """Re-run every eligibility rule on stored data with the current settings and time (the
    discovery pool step). A RECOMMENDABLE or INDEXED row whose eligibility flips swaps state
    (a transition: freshness sees it); a STALE row keeps STALE, its refresh decides the state.
    Rows another transaction has locked are skipped, never waited for. Returns the changes."""
    cfg = FilterConfig.from_settings()
    # One UPDATE per distinct outcome (a handful), not one per changed row: a settings change
    # can flip a whole pool.
    changes: dict[tuple[tuple[str, object], ...], list[int]] = {}
    with transaction.atomic():
        rows = (
            Repository.objects.filter(pk__in=list(repo_ids), lifecycle__in=RECHECKABLE)
            .select_for_update(skip_locked=True, of=("self",))
            .annotate(has_dependencies=has_dependencies_annotation())
            .prefetch_related("topics")
            .order_by("github_id")
        )
        for repo in rows:
            reason = eligibility(repo, now=now, cfg=cfg) or ""
            if reason == repo.ineligible_reason and repo.is_eligible == (not reason):
                continue
            update: dict[str, object] = {"is_eligible": not reason, "ineligible_reason": reason}
            if repo.lifecycle != Lifecycle.STALE:
                update["lifecycle"] = Lifecycle.INDEXED if reason else Lifecycle.RECOMMENDABLE
                if update["lifecycle"] != repo.lifecycle:
                    update["lifecycle_changed_at"] = now
            changes.setdefault(tuple(sorted(update.items())), []).append(repo.pk)
        for update_items, pks in changes.items():
            Repository.objects.filter(pk__in=pks).update(**dict(update_items))
    return sum(len(pks) for pks in changes.values())
