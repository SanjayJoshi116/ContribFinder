"""Housekeeping for tracked jobs."""

from celery import shared_task

from services.jobs import recover_stale_jobs as _recover


@shared_task(name="jobs.recover_stale_jobs")
def recover_stale_jobs() -> dict[str, int]:
    return _recover()
