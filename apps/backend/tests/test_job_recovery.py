"""Job heartbeat and recovery of jobs whose worker died."""

from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from github import tasks as github_tasks
from jobs import tasks
from jobs.models import SyncJob
from repositories import tasks as repo_tasks
from services.errors import JobCancelled
from services.job_guard import heartbeat

pytestmark = pytest.mark.django_db


def make_job(
    user, job_type: str, status: str, *, age: timedelta, attempts: int = 1, **fields
) -> SyncJob:
    job = SyncJob.objects.create(
        user=user, job_type=job_type, status=status, attempts=attempts, **fields
    )
    SyncJob.objects.filter(pk=job.pk).update(updated_at=timezone.now() - age)
    return job


def test_heartbeat_refreshes_running_job(user) -> None:
    job = make_job(user, "repository_discovery", "RUNNING", age=timedelta(hours=1))
    heartbeat(job)
    job.refresh_from_db()
    assert job.updated_at > timezone.now() - timedelta(minutes=1)


def test_heartbeat_reports_cancellation_without_touching(user) -> None:
    job = make_job(user, "repository_discovery", "CANCELLED", age=timedelta(hours=1))
    with pytest.raises(JobCancelled):
        heartbeat(job)
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
    exhausted = make_job(
        user,
        "profile_analysis",
        "RUNNING",
        age=timedelta(hours=1),
        attempts=3,
        steps={"analysis": "running"},
    )

    assert tasks.recover_stale_jobs() == {"requeued": 1, "failed": 1}
    assert queued == [("discovery", dead.pk)]
    exhausted.refresh_from_db()
    assert (exhausted.status, exhausted.error_code) == ("FAILED", "worker_lost")
    assert exhausted.steps == {"analysis": "failed"}
    alive.refresh_from_db()
    assert alive.status == "RUNNING"
    dead.refresh_from_db()
    assert (dead.status, dead.claim_token) == ("RETRYING", None)

    # The next run does not send the requeued job again.
    assert tasks.recover_stale_jobs() == {"requeued": 0, "failed": 0}
    assert queued == [("discovery", dead.pk)]


@override_settings(SYNC_STALE_AFTER_SECONDS=600, GITHUB_MAX_RETRY_DELAY=900)
def test_recover_requeues_lost_queued_jobs_once(user, monkeypatch) -> None:
    queued: list[int] = []
    monkeypatch.setattr(github_tasks.sync_github_profile, "delay", queued.append)
    monkeypatch.setattr(repo_tasks.generate_candidates, "delay", queued.append)
    lost = make_job(user, "github_profile_sync", "PENDING", age=timedelta(minutes=30))
    scheduled = make_job(user, "repository_discovery", "RETRYING", age=timedelta(minutes=20))

    assert tasks.recover_stale_jobs() == {"requeued": 1, "failed": 0}
    assert queued == [lost.pk]  # the RETRYING job may still be waiting for its countdown
    lost.refresh_from_db()
    assert lost.status == "PENDING"
    assert lost.updated_at > timezone.now() - timedelta(minutes=1)

    assert tasks.recover_stale_jobs() == {"requeued": 0, "failed": 0}
    assert queued == [lost.pk]
    assert scheduled.pk not in queued


@override_settings(SYNC_STALE_AFTER_SECONDS=600)
def test_requeued_job_is_reclaimed(user) -> None:
    from services.jobs import claim_job

    dead = make_job(user, "repository_discovery", "RUNNING", age=timedelta(minutes=20))
    assert claim_job(dead.pk)
    dead.refresh_from_db()
    assert (dead.status, dead.attempts) == ("RUNNING", 2)
    assert claim_job(dead.pk) is None  # now fresh: a duplicate delivery does nothing


@override_settings(SYNC_STALE_AFTER_SECONDS=600, SYNC_MAX_ATTEMPTS=3)
def test_redelivery_past_attempt_limit_fails_without_running(user) -> None:
    from services.jobs import claim_job

    dead = make_job(
        user,
        "github_profile_sync",
        "RUNNING",
        age=timedelta(minutes=20),
        attempts=3,
        steps={"profile": "done", "repositories": "running"},
    )
    assert claim_job(dead.pk) is None
    dead.refresh_from_db()
    assert (dead.status, dead.error_code, dead.attempts) == ("FAILED", "worker_lost", 3)
    assert dead.steps == {"profile": "done", "repositories": "failed"}
    assert dead.completed_at is not None
