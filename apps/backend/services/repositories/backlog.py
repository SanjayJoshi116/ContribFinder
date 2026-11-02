"""Background upkeep of shared candidate-repository data (design D8): which repositories go
STALE and which are due for a refresh. The Celery tasks in ``repositories/tasks.py`` only
dispatch what this returns.

A queued refresh is stamped (``refresh_queued_at``) and not queued again while its task can
still claim and finish, retries included: ``job_guard.lost_before``, the window a job's
requeue uses too. A completed or failed analysis clears the stamp; recovering an
abandoned claim never waits for it.

A repository that gave up its name is queued when the name is released
(``queue_released``), not an hour later by ``mark_stale`` and ``queue_batch``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q, QuerySet

from repositories.models import Lifecycle, Repository, RepositoryCandidate
from services.github.oauth import has_app_credentials
from services.job_guard import lost_before

from .lifecycle import IN_PROGRESS, abandoned_claims
from .staleness import stale_parts

Kind = Literal["all", "readme", "issues"]
# Recorded when GitHub rejects the app's client credentials during a refresh.
AUTH_INVALID = "github_auth_invalid"


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
    refresh = Q(lifecycle=Lifecycle.STALE) | Q(
        lifecycle=Lifecycle.DISCOVERED, lifecycle_changed_at__lt=grace
    )
    # A failed refresh waits its delay; FAILED retries and dead-worker claims don't.
    refresh &= ~_refresh_failed(now)
    waiting = refresh | Q(lifecycle=Lifecycle.FAILED, lifecycle_changed_at__lt=retry)
    batch = _pick(
        (waiting & _not_queued(now)) | abandoned_claims(now),
        now,
        order=(F("lifecycle_changed_at").asc(), "pk"),
        limit=settings.REPO_REFRESH_BATCH,
    )
    return [(pk, _kind(parts)) for pk, parts in batch]


def queue_released(pks: list[int], now: datetime, *, requeue: bool = False) -> list[int]:
    """Queue the refresh of pooled repositories that just gave up their name
    (``lifecycle.release_name``), inside the caller's transaction: the stamp rolls back with
    it, and the tasks are sent only once it commits. Holders another analysis holds (it ends
    in ``NameChanged`` and calls this with ``requeue``: its own stamp no longer counts),
    FAILED ones (their retry fetches everything) and already queued ones are left to those
    paths. A recent refresh failure does not hold it back, unless the app credentials were
    rejected (the refresh would fail the same way). Without app credentials or a worker
    (tasks run inline) nothing is queued: storing a repository never runs another
    repository's analysis, and the periodic task catches up."""
    if not pks or not has_app_credentials() or settings.CELERY_TASK_ALWAYS_EAGER:
        return []
    due = Q(pk__in=pks) & ~Q(lifecycle__in=[*IN_PROGRESS, Lifecycle.FAILED])
    due &= ~_refresh_failed(now, codes=[AUTH_INVALID])
    if not requeue:
        due &= _not_queued(now)
    picked = [pk for pk, _ in _pick(due, now, order=("pk",), limit=None)]
    if picked:

        def send() -> None:
            from repositories.tasks import sync_repository  # avoid import cycle

            for pk in picked:
                sync_repository.delay(pk)

        transaction.on_commit(send)
    return picked


def mark_queued(pks: list[int], now: datetime) -> None:
    """Renew the queued time: a refresh that scheduled a retry can still run until a full
    waiting period after the retry. Advisory: the analysis claim still fences the work."""
    Repository.objects.filter(pk__in=pks).update(refresh_queued_at=now)


def unmark_queued(pks: list[int]) -> None:
    """The broker refused these refreshes: nothing will run, so the next run may queue them."""
    if pks:
        Repository.objects.filter(pk__in=pks).update(refresh_queued_at=None)


def _not_queued(now: datetime) -> Q:
    """A queued task that can still run is not queued twice."""
    return ~Q(refresh_queued_at__gte=lost_before(now))


def _refresh_failed(now: datetime, *, codes: list[str] | None = None) -> Q:
    """A refresh failure recorded within its retry delay (``codes`` narrows the error)."""
    failed = Q(refresh_failed_at__gte=now - timedelta(minutes=settings.REPO_REFRESH_RETRY_MINUTES))
    return failed & Q(lifecycle_error__in=codes) if codes is not None else failed


def _pick(
    condition: Q, now: datetime, *, order: tuple[Any, ...], limit: int | None
) -> list[tuple[int, list[str]]]:
    """Lock, pick and stamp pooled repositories matching ``condition`` in one transaction,
    skipping rows another run is picking: overlapping runs never queue the same repository
    twice."""
    with transaction.atomic():
        rows = (
            pooled()
            .filter(condition)
            .order_by(*order)
            .select_for_update(skip_locked=True)
            .values_list("pk", "stale_parts")
        )
        batch = list(rows if limit is None else rows[:limit])
        Repository.objects.filter(pk__in=[pk for pk, _ in batch]).update(refresh_queued_at=now)
    return batch


def _kind(parts: list[str]) -> Kind:
    if parts == ["readme"]:
        return "readme"
    if parts == ["issues"]:
        return "issues"
    return "all"
