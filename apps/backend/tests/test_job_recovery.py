"""Job heartbeat and recovery of jobs whose worker died."""

from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from github import tasks as github_tasks
from jobs import tasks
from jobs.models import SyncJob
from repositories import tasks as repo_tasks

pytestmark = pytest.mark.django_db


def make_job(user, job_type: str, status: str, *, age: timedelta, attempts: int = 1) -> SyncJob:
    job = SyncJob.objects.create(user=user, job_type=job_type, status=status, attempts=attempts)
    SyncJob.objects.filter(pk=job.pk).update(updated_at=timezone.now() - age)
    return job


def test_heartbeat_refreshes_running_job(user) -> None:
    job = make_job(user, "repository_discovery", "RUNNING", age=timedelta(hours=1))
    assert job.heartbeat() == "RUNNING"
    job.refresh_from_db()
    assert job.updated_at > timezone.now() - timedelta(minutes=1)


def test_heartbeat_reports_cancellation_without_touching(user) -> None:
    job = make_job(user, "repository_discovery", "CANCELLED", age=timedelta(hours=1))
    assert job.heartbeat() == "CANCELLED"
    job.refresh_from_db()
    assert job.updated_at < timezone.now() - timedelta(minutes=59)


@override_settings(SYNC_STALE_AFTER_SECONDS=600, SYNC_MAX_ATTEMPTS=3)
def test_recover_requeues_dead_jobs_and_fails_exhausted_ones(user, monkeypatch) -> None:
    queued: list[tuple[str, int]] = []
    monkeypatch.setattr(
        repo_tasks.generate_candidates, "delay", lambda pk: queued.append(("discovery", pk))
    )
    monkeypatch.setattr(
        github_tasks.sync_github_profile, "delay", lambda pk: queued.append(("sync", pk))
    )
    dead = make_job(user, "repository_discovery", "RUNNING", age=timedelta(minutes=20))
    alive = make_job(user, "github_profile_sync", "RUNNING", age=timedelta(minutes=2))
    make_job(user, "github_profile_sync", "COMPLETED", age=timedelta(days=1))
    exhausted = make_job(user, "profile_analysis", "RUNNING", age=timedelta(hours=1), attempts=3)

    assert tasks.recover_stale_jobs() == {"requeued": 1, "failed": 1}
    assert queued == [("discovery", dead.pk)]
    exhausted.refresh_from_db()
    assert (exhausted.status, exhausted.error_code) == ("FAILED", "worker_lost")
    alive.refresh_from_db()
    assert alive.status == "RUNNING"


@override_settings(SYNC_STALE_AFTER_SECONDS=600)
def test_requeued_job_is_reclaimed(user) -> None:
    from services.jobs import claim_job

    dead = make_job(user, "repository_discovery", "RUNNING", age=timedelta(minutes=20))
    assert claim_job(dead.pk)
    dead.refresh_from_db()
    assert (dead.status, dead.attempts) == ("RUNNING", 2)
    assert not claim_job(dead.pk)  # now fresh: a duplicate delivery does nothing
