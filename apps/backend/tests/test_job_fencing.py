"""Claim fencing for jobs and repository analyses, job ending, starting and overlapping
profile analyses (change job-claim-fencing)."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError
from django.test import override_settings
from django.utils import timezone

from developers.models import DeveloperProfile, Interest, Skill
from developers.tasks import extract_developer_skills
from github.tasks import sync_github_profile
from jobs.models import SyncJob
from repositories import tasks as repo_tasks
from repositories.models import Lifecycle, Repository
from services import jobs
from services.errors import JobCancelled
from services.github.errors import GitHubRateLimited
from services.github.sync import initial_steps
from services.job_guard import heartbeat, job_write, save_progress
from services.profiling.analysis import ProfileAnalysisService
from services.repositories import lifecycle
from services.repositories.analysis import Outcome, RepositoryAnalysisService

from .repo_fixtures import API, add_candidate, make_candidate_repo, mock_repo_api
from .test_repository_analysis import analyze, client, profile  # noqa: F401  (fixtures)

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]

SYNC = SyncJob.JobType.GITHUB_PROFILE_SYNC
ANALYSIS = SyncJob.JobType.PROFILE_ANALYSIS


def age(job: SyncJob, by: timedelta = timedelta(hours=1)) -> None:
    SyncJob.objects.filter(pk=job.pk).update(updated_at=timezone.now() - by)


# --- Job claims ------------------------------------------------------------------------


def test_reclaimed_worker_is_refused_every_write(user) -> None:
    job = SyncJob.objects.create(user=user, job_type=SYNC, status="PENDING")
    first = jobs.claim_job(job.pk)
    assert first is not None
    age(job)
    second = jobs.claim_job(job.pk)
    assert second is not None and second.claim_token != first.claim_token

    with pytest.raises(JobCancelled):
        heartbeat(first)
    with pytest.raises(JobCancelled):
        save_progress(first, steps={"profile": "done"})
    with pytest.raises(JobCancelled), job_write(first):
        pytest.fail("the body must not run")
    assert jobs.finish_job(first, "COMPLETED") is False

    heartbeat(second)
    assert jobs.finish_job(second, "COMPLETED") is True
    job.refresh_from_db()
    assert (job.status, job.claim_token) == ("COMPLETED", None)


def test_reclaimed_worker_starts_no_follow_up(user) -> None:
    job = SyncJob.objects.create(user=user, job_type=SYNC, status="PENDING")
    follow_ups: list[int] = []

    def runner(claimed: SyncJob) -> None:
        # Another worker reclaims the job while this one is still working.
        age(claimed)
        assert jobs.claim_job(claimed.pk) is not None

    jobs.run_tracked_job(MagicMock(), job.pk, runner, on_completed=lambda j: follow_ups.append(1))
    job.refresh_from_db()
    assert job.status == "RUNNING"  # still owned by the second worker
    assert follow_ups == []


def test_eager_mode_never_retries_inline(user, respx_mock) -> None:
    job = SyncJob.objects.create(user=user, job_type=SYNC, status="PENDING", steps=initial_steps())
    route = respx_mock.get(f"{API}/user").respond(429, headers={"Retry-After": "60"})
    sync_github_profile.delay(job.pk)
    job.refresh_from_db()
    assert (job.status, job.error_code) == ("FAILED", "github_rate_limited")
    assert route.call_count == 1
    assert "running" not in job.steps.values()


# --- Ending jobs ---------------------------------------------------------------------------


def test_cancel_marks_running_steps_failed(user) -> None:
    job = SyncJob.objects.create(
        user=user,
        job_type=SYNC,
        status="RUNNING",
        steps={"profile": "done", "repositories": "running", "languages": "pending"},
    )
    assert jobs.cancel_active_syncs(user) == 1
    job.refresh_from_db()
    assert job.status == "CANCELLED"
    assert job.steps == {"profile": "done", "repositories": "failed", "languages": "pending"}
    assert job.completed_at is not None


# --- Starting jobs -------------------------------------------------------------------------


@override_settings(SYNC_STALE_AFTER_SECONDS=600)
def test_stale_analysis_does_not_block_reanalysis(user, django_capture_on_commit_callbacks) -> None:
    stale = SyncJob.objects.create(
        user=user, job_type=ANALYSIS, status="RUNNING", steps={"analysis": "running"}
    )
    age(stale, timedelta(minutes=20))
    with (
        patch("developers.tasks.extract_developer_skills.delay") as delay,
        django_capture_on_commit_callbacks(execute=True),
    ):
        job, created = jobs.start_profile_analysis(user)
    assert created and job.pk != stale.pk
    delay.assert_called_once_with(job.pk)
    stale.refresh_from_db()
    assert (stale.status, stale.error_code, stale.steps) == (
        "FAILED",
        "worker_lost",
        {"analysis": "failed"},
    )


def test_start_returns_conflicting_job_that_finished_meanwhile(user) -> None:
    finished = SyncJob.objects.create(user=user, job_type=SYNC, status="FAILED")
    with patch.object(SyncJob.objects, "create", side_effect=IntegrityError("conflict")):
        job, created = jobs.start_profile_sync(user)
    assert (job.pk, created) == (finished.pk, False)


# --- Profile analysis ----------------------------------------------------------------------


def test_older_analysis_does_not_overwrite_newer_profile(synced) -> None:
    ProfileAnalysisService(synced).run()
    newer = timezone.now() + timedelta(hours=1)
    DeveloperProfile.objects.filter(user=synced).update(analyzed_at=newer, summary="newer")

    job = SyncJob.objects.create(user=synced, job_type=ANALYSIS, steps={"analysis": "pending"})
    with patch("developers.tasks.start_discovery_after") as follow_up:
        extract_developer_skills.delay(job.pk)

    stored = DeveloperProfile.objects.get(user=synced)
    assert (stored.analyzed_at, stored.summary) == (newer, "newer")
    job.refresh_from_db()
    assert (job.status, job.steps) == ("COMPLETED", {"analysis": "done"})
    follow_up.assert_called_once()  # completes normally: the newer profile already covers it


def test_catalog_rows_are_upserted_in_sorted_order(synced) -> None:
    seen: dict[str, list[str]] = {}

    def recorder(model: Any) -> Any:
        original = model.objects.bulk_create

        def bulk_create(objs: Any, *args: Any, **kwargs: Any) -> Any:
            objs = list(objs)
            seen[model.__name__] = [o.slug for o in objs]
            return original(objs, *args, **kwargs)

        return patch.object(model.objects, "bulk_create", side_effect=bulk_create)

    with recorder(Skill), recorder(Interest):
        ProfileAnalysisService(synced).run()
    assert seen["Skill"] and seen["Skill"] == sorted(set(seen["Skill"]))
    assert seen["Interest"] and seen["Interest"] == sorted(set(seen["Interest"]))


# --- Repository claims ---------------------------------------------------------------------


def age_claim(repo: Repository, by: timedelta = timedelta(hours=1)) -> None:
    Repository.objects.filter(pk=repo.pk).update(claimed_at=timezone.now() - by)


def test_renewed_claim_is_not_reclaimed() -> None:
    repo = make_candidate_repo(7)
    claimed = lifecycle.claim(repo.pk)
    assert claimed is not None
    age_claim(repo)
    lifecycle.renew(claimed)
    assert lifecycle.claim(repo.pk) is None


def test_reclaimed_analysis_changes_nothing() -> None:
    repo = make_candidate_repo(7)
    first = lifecycle.claim(repo.pk)
    assert first is not None
    age_claim(repo)
    second = lifecycle.claim(repo.pk)
    assert second is not None

    lifecycle.release(first)
    lifecycle.fail(first, "not_found")
    with pytest.raises(lifecycle.ClaimLost):
        lifecycle.renew(first)
    with pytest.raises(lifecycle.ClaimLost):
        lifecycle.hold(first)

    repo.refresh_from_db()
    assert (repo.lifecycle, repo.claim_token, repo.lifecycle_error) == (
        Lifecycle.FETCHING,
        second.claim_token,
        "",
    )


def test_analysis_reclaimed_mid_fetch_stores_nothing(client, respx_mock) -> None:  # noqa: F811
    repo = make_candidate_repo(7, "encode/httpx")
    mock_repo_api(respx_mock, "encode/httpx", 7)
    calls = 0

    def reclaim_once() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:  # after the metadata part: another worker takes over
            age_claim(repo)
            assert lifecycle.claim(repo.pk) is not None

    service = RepositoryAnalysisService(client, check_cancelled=reclaim_once)
    assert service.run(repo.pk) == Outcome.SKIPPED
    repo.refresh_from_db()
    assert repo.lifecycle == Lifecycle.FETCHING  # the new owner's claim is untouched
    assert not repo.snapshots.exists()


def test_release_restores_discovered_when_nothing_was_saved() -> None:
    repo = make_candidate_repo(7)
    claimed = lifecycle.claim(repo.pk)
    assert claimed is not None
    Repository.objects.filter(pk=repo.pk).update(previous_lifecycle="")
    lifecycle.release(claimed)
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.claim_token, repo.claimed_at) == (Lifecycle.DISCOVERED, None, None)


def test_transient_failure_keeps_the_failed_retry_clock(client, respx_mock) -> None:  # noqa: F811
    failed_at = timezone.now() - timedelta(days=2)
    repo = make_candidate_repo(
        7,
        "encode/httpx",
        lifecycle="failed",
        lifecycle_changed_at=failed_at,
        is_eligible=False,
        lifecycle_error="not_found",
    )
    routes = mock_repo_api(respx_mock, "encode/httpx", 7)
    routes["labels"].respond(429, headers={"Retry-After": "60"})
    with pytest.raises(GitHubRateLimited):
        analyze(client, repo)
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.lifecycle_changed_at) == (Lifecycle.FAILED, failed_at)


@override_settings(REPO_DISCOVERED_GRACE_MINUTES=10)
def test_released_discovered_repository_stays_due(client, respx_mock, profile, monkeypatch) -> None:  # noqa: F811
    found_at = timezone.now() - timedelta(hours=2)
    repo = make_candidate_repo(7, "encode/httpx", lifecycle_changed_at=found_at)
    add_candidate(profile, repo)
    routes = mock_repo_api(respx_mock, "encode/httpx", 7)
    routes["labels"].respond(429, headers={"Retry-After": "60"})
    with pytest.raises(GitHubRateLimited):
        analyze(client, repo)
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.lifecycle_changed_at) == (Lifecycle.DISCOVERED, found_at)

    queued: list[int] = []
    monkeypatch.setattr(repo_tasks.sync_repository, "delay", queued.append)
    repo_tasks.process_repository_backlog()
    assert queued == [repo.pk]
