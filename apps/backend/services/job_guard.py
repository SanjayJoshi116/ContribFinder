"""Writes of a user's data inside a job happen only while the job is RUNNING (design D1).

Deletion cancels the user's jobs first (an UPDATE of the same row), so a write in flight either
commits before the deletion, which then removes it, or sees the cancellation and writes nothing.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from django.db import transaction
from django.utils import timezone

from jobs.models import SyncJob

from .errors import JobCancelled


@contextmanager
def job_write(job_id: int) -> Iterator[None]:
    """A transaction holding the job's row lock; raises JobCancelled unless it is RUNNING.

    Wrap only the write block: never network I/O, so deletion never waits on GitHub."""
    with transaction.atomic():
        status = (
            SyncJob.objects.select_for_update()
            .filter(pk=job_id)
            .values_list("status", flat=True)
            .first()
        )
        if status != SyncJob.Status.RUNNING:
            raise JobCancelled()
        yield


def save_progress(job: SyncJob, **fields: Any) -> None:
    """Store progress fields (steps, metadata) of a RUNNING job, which also counts as a
    heartbeat. Raises JobCancelled when the job was cancelled or deleted meanwhile."""
    updated = SyncJob.objects.filter(pk=job.pk, status=SyncJob.Status.RUNNING).update(
        **fields, updated_at=timezone.now()
    )
    if not updated:
        raise JobCancelled()
