"""Task sends and final-failure logs (change task-dispatch-and-failure-logs)."""

import logging
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.db import DatabaseError, transaction
from django.test import override_settings
from django.utils import timezone
from kombu.exceptions import OperationalError as BrokerError

from accounts.models import User
from developers.models import DeveloperProfile
from e2e.builders import make_candidate_repo
from feedback.models import DismissedRepository
from github.tasks import revoke_later, revoke_replaced_token
from jobs.models import SyncJob
from services import dispatch, feedback, jobs
from services.crypto import encrypt_token
from services.errors import PermanentJobError, log_failure
from services.github.accounts import queue_revocation
from services.github.errors import GitHubTransientError
from services.github.oauth import OAuthError

from .factories import UserFactory
from .test_github_auth import TOKEN, assert_no_secrets
from .test_job_recovery import make_job

pytestmark = pytest.mark.django_db

SECRET_ARG = "ciphertext-never-logged"


def refusing(*args: Any, **kwargs: Any) -> None:
    raise BrokerError("broker down")


def task(**methods: Any) -> MagicMock:
    mock = MagicMock(**methods)
    mock.name = "app.example"
    return mock


# --- services.dispatch ------------------------------------------------------------------


def test_send_delays_and_reports_sent() -> None:
    sent = task()
    assert dispatch.send(sent, 7) is True
    sent.delay.assert_called_once_with(7)


def test_send_with_options_uses_apply_async() -> None:
    sent = task()
    assert dispatch.send(sent, 7, countdown=30) is True
    sent.apply_async.assert_called_once_with((7,), countdown=30)


def test_refused_send_is_logged_without_its_arguments(caplog) -> None:
    refused = task(**{"delay.side_effect": refusing})
    with caplog.at_level(logging.WARNING):
        assert dispatch.send(refused, SECRET_ARG, about="job 3") is False
    record = next(r for r in caplog.records if r.name == "services.dispatch")
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "Task app.example not queued (job 3)"
    assert record.exc_info is not None and record.exc_info[0] is BrokerError
    assert SECRET_ARG not in caplog.text


def test_other_send_errors_propagate() -> None:
    broken = task(**{"delay.side_effect": TypeError("not serializable")})
    with pytest.raises(TypeError):
        dispatch.send(broken, 1)


def test_after_commit_sends_on_commit_only(django_capture_on_commit_callbacks) -> None:
    sent = task()
    with django_capture_on_commit_callbacks(execute=True):
        dispatch.after_commit(sent, 1)
        sent.delay.assert_not_called()
    sent.delay.assert_called_once_with(1)


def test_after_commit_sends_nothing_on_rollback(django_capture_on_commit_callbacks) -> None:
    sent = task()
    with (
        django_capture_on_commit_callbacks(execute=True) as callbacks,
        pytest.raises(RuntimeError),
        transaction.atomic(),
    ):
        dispatch.after_commit(sent, 1)
        raise RuntimeError
    assert callbacks == []
    sent.delay.assert_not_called()


# --- A refused send never fails committed work -----------------------------------------


def test_sync_started_while_the_broker_is_down(
    signed_in_client, user: User, caplog, django_capture_on_commit_callbacks
) -> None:
    with (
        patch("github.tasks.sync_github_profile.delay", side_effect=refusing),
        django_capture_on_commit_callbacks(execute=True),
    ):
        response = signed_in_client.post("/api/v1/profile/sync")
    assert response.status_code == 202
    job = SyncJob.objects.get(user=user, job_type=jobs.SYNC)
    assert job.status == SyncJob.Status.PENDING
    assert f"Task github.sync_github_profile not queued (job {job.pk})" in caplog.text


def test_restore_while_the_broker_is_down(
    user: User, caplog, django_capture_on_commit_callbacks
) -> None:
    DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())
    repository = make_candidate_repo(1)
    DismissedRepository.objects.create(user=user, repository=repository)
    with (
        patch("recommendations.tasks.generate_recommendations.delay", side_effect=refusing),
        django_capture_on_commit_callbacks(execute=True),
    ):
        assert feedback.restore(user, repository.pk) is True
    assert not DismissedRepository.objects.filter(user=user).exists()
    job = SyncJob.objects.get(user=user, job_type=jobs.RECOMMENDATIONS)
    assert job.status == SyncJob.Status.PENDING
    assert "Task recommendations.generate_recommendations not queued" in caplog.text


@override_settings(SYNC_STALE_AFTER_SECONDS=600)
def test_recovery_continues_past_a_refused_send(caplog) -> None:
    waiting = [
        make_job(UserFactory(), jobs.SYNC, "PENDING", age=timedelta(days=1)).pk for _ in range(3)
    ]
    sent: list[int] = []

    def delay(pk: int) -> None:
        if pk == waiting[1]:
            raise BrokerError("broker down")
        sent.append(pk)

    with patch("github.tasks.sync_github_profile.delay", side_effect=delay):
        result = jobs.recover_stale_jobs()

    assert result == {"requeued": 2, "failed": 0}
    assert sorted(sent) == [waiting[0], waiting[2]]
    assert f"not queued (job {waiting[1]})" in caplog.text


def test_database_error_while_starting_a_job_is_raised(user: User) -> None:
    with (
        patch.object(jobs, "new_job", side_effect=DatabaseError("connection lost")),
        pytest.raises(DatabaseError),
    ):
        jobs.start_profile_sync(user, enforce_cooldown=False)


# --- Final-failure logs -----------------------------------------------------------------

logger = logging.getLogger("tests.failures")


def test_unexpected_failure_logs_an_error_with_traceback(caplog) -> None:
    exc = ValueError("bug")
    log_failure(logger, "internal_error", exc, "Thing %s failed", 1)
    (record,) = caplog.records
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "Thing 1 failed: internal_error"
    assert record.exc_info is not None and record.exc_info[1] is exc


@pytest.mark.parametrize(
    ("code", "exc", "expected"),
    [
        ("github_unavailable", GitHubTransientError("GET /x returned 502"), ()),
        ("internal_error", OAuthError("refused", "token=abc"), (OAuthError,)),
        ("profile_missing", PermanentJobError("no profile yet"), ()),
    ],
)
def test_expected_failure_logs_a_warning_without_traceback(
    caplog, code: str, exc: Exception, expected: tuple[type[BaseException], ...]
) -> None:
    log_failure(logger, code, exc, "Thing failed", expected=expected)
    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert record.exc_info is None
    assert record.getMessage() == f"Thing failed: {code} ({type(exc).__name__})"
    assert str(exc) not in record.getMessage()


def test_bug_in_a_tracked_job_keeps_its_traceback(user: User, caplog) -> None:
    job = jobs.new_job(user, jobs.SYNC)

    def runner(job: SyncJob) -> None:
        raise ValueError("bug in sync")

    jobs.run_tracked_job(MagicMock(), job.pk, runner)

    job.refresh_from_db()
    assert (job.status, job.error_code) == (SyncJob.Status.FAILED, "internal_error")
    record = next(r for r in caplog.records if r.getMessage().startswith(f"Job {job.pk} failed"))
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None and record.exc_info[0] is ValueError


def test_github_refusing_a_revocation_logs_a_warning_without_the_token(caplog) -> None:
    with (
        caplog.at_level(logging.DEBUG),
        patch("github.tasks.revoke", side_effect=OAuthError("revoke_failed", "refused")),
    ):
        revoke_later.apply(args=(encrypt_token(TOKEN), None, True), throw=True)
    record = next(r for r in caplog.records if r.name == "github.tasks")
    assert record.levelno == logging.WARNING
    assert record.exc_info is None
    assert_no_secrets(caplog.text)
    assert all(TOKEN not in r.getMessage() for r in caplog.records)


def test_a_bare_permanent_job_error_logs_a_warning(user: User, caplog) -> None:
    """CR9-3: a typed job error with the default code is expected, not a bug."""
    job = jobs.new_job(user, jobs.SYNC)

    def runner(job: SyncJob) -> None:
        raise PermanentJobError("no profile yet")

    jobs.run_tracked_job(MagicMock(), job.pk, runner)

    job.refresh_from_db()
    assert (job.status, job.error_code) == (SyncJob.Status.FAILED, "internal_error")
    record = next(r for r in caplog.records if r.getMessage().startswith(f"Job {job.pk} failed"))
    assert record.levelno == logging.WARNING
    assert record.exc_info is None
    assert "no profile yet" not in record.getMessage()


def test_a_revocation_send_error_never_fails_committed_work(
    django_capture_on_commit_callbacks, caplog
) -> None:
    """CR9-1: any send error is logged; later on-commit callbacks (a deletion's cache purge)
    still run."""
    later = MagicMock()
    with (
        patch("github.tasks.revoke_later.delay", side_effect=RuntimeError("bug")),
        django_capture_on_commit_callbacks(execute=True),
    ):
        queue_revocation(encrypt_token(TOKEN), 1, grant=False)
        transaction.on_commit(later)
    later.assert_called_once()
    assert "RuntimeError" in caplog.text
    assert_no_secrets(caplog.text)


def test_a_replaced_token_revocation_goes_through_dispatch(caplog) -> None:
    """CR9-5: an old queued message's resend is logged on refusal, not raised."""
    with patch("github.tasks.revoke_later.delay", side_effect=refusing):
        revoke_replaced_token(1, SECRET_ARG)
    assert "Task github.revoke_later not queued (token revocation)" in caplog.text
    assert SECRET_ARG not in caplog.text


@override_settings(SYNC_STALE_AFTER_SECONDS=600)
def test_a_refused_requeue_is_not_logged_as_requeued(caplog) -> None:
    """CR9-6."""
    job = make_job(UserFactory(), jobs.SYNC, "PENDING", age=timedelta(days=1))
    with patch("github.tasks.sync_github_profile.delay", side_effect=refusing):
        assert jobs.recover_stale_jobs() == {"requeued": 0, "failed": 0}
    assert f"Job {job.pk} (sync) was never picked up; requeued" not in caplog.text
