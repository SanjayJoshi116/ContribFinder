"""Writes of a user's data inside a job happen only while the job is RUNNING and only by the
worker holding its current claim (privacy-deletion-finality D1, job-claim-fencing D1).

Deletion cancels the user's jobs first (an UPDATE of the same row), so a write in flight either
commits before the deletion, which then removes it, or sees the cancellation and writes nothing.
A reclaim replaces the claim token, so a worker that lost its claim is refused the same way.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import F, Func, JSONField, QuerySet, Value
from django.utils import timezone

from jobs.models import SyncJob

from .errors import JobCancelled


def stale_before(now: datetime) -> datetime:
    """Work (a job's heartbeat, a repository claim) last updated before this is a dead
    worker's and may be reclaimed."""
    return now - timedelta(seconds=settings.SYNC_STALE_AFTER_SECONDS)


def is_stalled(job: SyncJob, now: datetime) -> bool:
    """The job is RUNNING with no heartbeat since ``stale_before``: its worker died (or is too
    slow). ``services.jobs._stale_running`` is the same rule as a query."""
    return job.status == SyncJob.Status.RUNNING and job.updated_at < stale_before(now)


def lost_before(now: datetime) -> datetime:
    """Queued work (a job's message, a repository refresh task) untouched since before this
    has had its chance to be claimed and retried: its message was lost, so it may be queued
    again."""
    return stale_before(now) - timedelta(seconds=settings.GITHUB_MAX_RETRY_DELAY)


def held(job: SyncJob) -> QuerySet[SyncJob]:
    """The job's row, if it is still RUNNING under this worker's claim."""
    return SyncJob.objects.filter(
        pk=job.pk, status=SyncJob.Status.RUNNING, claim_token=job.claim_token
    )


@contextmanager
def job_write(job: SyncJob) -> Iterator[None]:
    """A transaction holding the job's row lock; raises JobCancelled unless the job is RUNNING
    under this worker's claim.

    Wrap only the write block: never network I/O, so deletion never waits on GitHub."""
    with transaction.atomic():
        if not held(job).select_for_update().values_list("pk", flat=True).first():
            raise JobCancelled()
        yield


def save_progress(job: SyncJob, **fields: Any) -> None:
    """Store progress fields of a RUNNING job, which also counts as a heartbeat. Raises
    JobCancelled when the job was cancelled, deleted or reclaimed. Metadata goes through
    ``merge_metadata``."""
    if not held(job).update(**fields, updated_at=timezone.now()):
        raise JobCancelled()


def merge_metadata(job: SyncJob, values: Mapping[str, Any], **fields: Any) -> None:
    """Merge ``values`` into the stored metadata of a RUNNING job (PostgreSQL ``||``): only
    the changed keys are sent, and keys another writer stored meanwhile are kept. ``fields``
    (steps) are stored in the same write. Counts as a heartbeat. Raises JobCancelled when the
    job was cancelled, deleted or reclaimed."""
    merged = Func(
        F("metadata"),
        Value(dict(values), output_field=JSONField()),
        template="(%(expressions)s)",
        arg_joiner=" || ",
        output_field=JSONField(),
    )
    save_progress(job, metadata=merged, **fields)
    job.metadata = {**job.metadata, **values}


def heartbeat(job: SyncJob) -> None:
    """Mark the job alive between units of work, so it is not reclaimed as a dead worker's.
    Raises JobCancelled when the job was cancelled, deleted or reclaimed."""
    save_progress(job)
