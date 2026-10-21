"""Background upkeep of shared candidate-repository data (design D8): which repositories go
STALE and which are due for a refresh. The Celery tasks in ``repositories/tasks.py`` only
dispatch what this returns.

A queued refresh is stamped (``refresh_queued_at``) and not queued again while its task can
still claim and finish, retries included: ``job_guard.lost_before``, the window a job's
requeue uses too. A completed or failed analysis clears the stamp; recovering an
abandoned claim never waits for it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q, QuerySet

from repositories.models import Lifecycle, Repository, RepositoryCandidate
from services.job_guard import lost_before

from .lifecycle import abandoned_claims
from .staleness import stale_parts

Kind = Literal["all", "readme", "issues"]


def pooled() -> QuerySet[Repository]:
    """Repositories in at least one developer's candidate pool (``Exists``, not a join with
    DISTINCT, so the rows can be locked)."""
    return Repository.objects.filter(
        Exists(RepositoryCandidate.objects.filter(repository=OuterRef("pk")))
    )


def mark_stale(now: datetime) -> int:
    """Move pooled RECOMMENDABLE/INDEXED repositories with stale data types to STALE."""
    marked = 0
    candidates = pooled().filter(lifecycle__in=[Lifecycle.RECOMMENDABLE, Lifecycle.INDEXED])
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
    return marked


def queue_batch(now: datetime) -> list[tuple[int, Kind]]:
    """Pick and stamp the next batch of pooled repositories that are stale, still unanalyzed
    after the grace period, failed and due for a retry, or left mid-analysis by a dead worker.
    Returns ``(repository id, kind)``: a refresh of only the README or only the issues when
    that is all that is stale, else of every stale part."""
    grace = now - timedelta(minutes=settings.REPO_DISCOVERED_GRACE_MINUTES)
    retry = now - timedelta(hours=settings.REPO_FAILED_RETRY_HOURS)
    refresh_retry = now - timedelta(minutes=settings.REPO_REFRESH_RETRY_MINUTES)
    refresh = Q(lifecycle=Lifecycle.STALE) | Q(
        lifecycle=Lifecycle.DISCOVERED, lifecycle_changed_at__lt=grace
    )
    # A failed refresh waits its delay; FAILED retries and dead-worker claims don't.
    refresh &= ~Q(refresh_failed_at__gte=refresh_retry)
    waiting = refresh | Q(lifecycle=Lifecycle.FAILED, lifecycle_changed_at__lt=retry)
    # A queued task that can still run is not queued twice.
    waiting &= ~Q(refresh_queued_at__gte=lost_before(now))
    # Picked and stamped in one transaction, skipping rows another backlog run is picking:
    # overlapping runs never queue the same repository twice.
    with transaction.atomic():
        batch = list(
            pooled()
            .filter(waiting | abandoned_claims(now))
            .order_by(F("lifecycle_changed_at").asc(), "pk")
            .select_for_update(skip_locked=True)
            .values_list("pk", "stale_parts")[: settings.REPO_REFRESH_BATCH]
        )
        Repository.objects.filter(pk__in=[pk for pk, _ in batch]).update(refresh_queued_at=now)
    return [(pk, _kind(parts)) for pk, parts in batch]


def _kind(parts: list[str]) -> Kind:
    if parts == ["readme"]:
        return "readme"
    if parts == ["issues"]:
        return "issues"
    return "all"
