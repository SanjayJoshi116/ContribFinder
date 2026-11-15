"""A job's follow-up commits with its outcome (change pipeline-progress-review-fixes, PIPE-1,
PIPE-2). Transactional tests: a second connection sees only what is committed."""

from collections.abc import Iterator
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from django.db import connections, transaction

from accounts.models import User
from jobs.models import SyncJob
from services import jobs
from services.errors import PermanentJobError

from .factories import UserFactory

pytestmark = pytest.mark.django_db(transaction=True)

SYNC = SyncJob.JobType.GITHUB_PROFILE_SYNC
DISCOVERY = SyncJob.JobType.REPOSITORY_DISCOVERY


@pytest.fixture
def other() -> Iterator[Any]:
    """Another database connection: it sees committed rows only."""
    connection = connections.create_connection("default")
    yield connection
    connection.close()


def committed(connection: Any, user: User) -> dict[str, str]:
    """The user's jobs (type → status) as another connection sees them."""
    assert SyncJob._meta.db_table == "jobs_syncjob"
    with connection.cursor() as cursor:
        cursor.execute("SELECT job_type, status FROM jobs_syncjob WHERE user_id = %s", [user.pk])
        return dict(cursor.fetchall())


def new_job(user: User) -> SyncJob:
    return SyncJob.objects.create(user=user, job_type=SYNC, status="PENDING")


def test_completion_is_not_visible_before_its_follow_up(other) -> None:
    user = cast(User, UserFactory())
    job = new_job(user)
    seen: dict[str, dict[str, str]] = {}

    def start_next(finished: SyncJob) -> None:
        seen["in hook"] = committed(other, user)
        jobs.new_job(user, DISCOVERY)
        transaction.on_commit(lambda: seen.setdefault("on send", committed(other, user)))

    jobs.run_tracked_job(MagicMock(), job.pk, lambda j: None, on_completed=start_next)

    # No gap: while the hook runs, the completion is not committed yet.
    assert seen["in hook"] == {SYNC: "RUNNING"}
    # The task is sent after the commit, which holds both.
    assert seen["on send"] == {SYNC: "COMPLETED", DISCOVERY: "PENDING"}
    assert committed(other, user) == {SYNC: "COMPLETED", DISCOVERY: "PENDING"}


def test_failure_and_its_follow_up_commit_together(other) -> None:
    user = cast(User, UserFactory())
    job = new_job(user)
    seen: list[dict[str, str]] = []

    def runner(claimed: SyncJob) -> None:
        raise PermanentJobError("bad")

    def rerun(finished: SyncJob) -> None:
        seen.append(committed(other, user))
        jobs.new_job(user, DISCOVERY)

    jobs.run_tracked_job(MagicMock(), job.pk, runner, on_failed=rerun)

    assert seen == [{SYNC: "RUNNING"}]
    assert committed(other, user) == {SYNC: "FAILED", DISCOVERY: "PENDING"}


def test_a_failing_follow_up_keeps_the_completion_and_drops_its_writes(other, caplog) -> None:
    user = cast(User, UserFactory())
    job = new_job(user)

    def broken(finished: SyncJob) -> None:
        jobs.new_job(user, DISCOVERY)
        raise RuntimeError("boom")

    jobs.run_tracked_job(MagicMock(), job.pk, lambda j: None, on_completed=broken)

    assert committed(other, user) == {SYNC: "COMPLETED"}
    assert f"Follow-up of job {job.pk} failed" in caplog.text


def test_a_refused_follow_up_task_keeps_the_completion(other, caplog) -> None:
    from kombu.exceptions import OperationalError

    user = cast(User, UserFactory())
    job = new_job(user)

    def refused() -> None:
        raise OperationalError("broker down")

    def start_next(finished: SyncJob) -> None:
        jobs.new_job(user, DISCOVERY)
        transaction.on_commit(refused)

    jobs.run_tracked_job(MagicMock(), job.pk, lambda j: None, on_completed=start_next)

    # Committed before the send failed; job recovery re-sends the PENDING follow-up.
    assert committed(other, user) == {SYNC: "COMPLETED", DISCOVERY: "PENDING"}
    assert f"Follow-up task of job {job.pk} not queued" in caplog.text


def test_a_follow_up_task_failing_inline_keeps_the_completion(other, caplog) -> None:
    # Eager mode runs the follow-up's task inline on commit; with propagation on, its error
    # must not escape the finished job (a request that ran the sync inline).
    user = cast(User, UserFactory())
    job = new_job(user)

    def broken_task() -> None:
        raise RuntimeError("inline task failed")

    def start_next(finished: SyncJob) -> None:
        jobs.new_job(user, DISCOVERY)
        transaction.on_commit(broken_task)

    jobs.run_tracked_job(MagicMock(), job.pk, lambda j: None, on_completed=start_next)

    assert committed(other, user) == {SYNC: "COMPLETED", DISCOVERY: "PENDING"}
    assert f"Follow-up of job {job.pk} failed" in caplog.text


def test_a_hook_locks_the_users_active_jobs_in_pk_order(other) -> None:
    # The hook may expire the user's stale jobs: their locks are taken before the finishing
    # job's own, in pk order, so a cancel locking the same rows in pk order cannot deadlock.
    user = cast(User, UserFactory())
    earlier = SyncJob.objects.create(user=user, job_type=DISCOVERY, status="RUNNING")
    job = new_job(user)
    assert earlier.pk < job.pk
    seen: dict[str, Any] = {}

    def start_next(finished: SyncJob) -> None:
        with other.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM jobs_syncjob WHERE id = %s FOR UPDATE SKIP LOCKED", [earlier.pk]
            )
            seen["free"] = cursor.fetchall()

    jobs.run_tracked_job(MagicMock(), job.pk, lambda j: None, on_completed=start_next)

    assert seen["free"] == []  # already locked by the finishing transaction
