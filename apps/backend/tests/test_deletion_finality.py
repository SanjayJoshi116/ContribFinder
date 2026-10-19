"""A running job never writes a user's data back after deletion (change
privacy-deletion-finality, design D1)."""

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from developers.models import DeveloperProfile
from developers.tasks import extract_developer_skills
from github.models import GitHubProfile
from jobs.models import SyncJob
from repositories.models import RepositoryCandidate
from services import profiling
from services.data_deletion import delete_github_data
from services.discovery.service import DiscoveryService
from services.errors import JobCancelled
from services.github.client import GitHubUser
from services.github.sync import GitHubSyncService, initial_steps
from services.job_guard import job_write
from services.profiling.analysis import ProfileAnalysisService

from .test_discovery_service import HTTPX, make_developer, mock_search, new_job
from .test_sync_api import make_job

pytestmark = pytest.mark.django_db

PROFILE = {"id": 424242, "login": "octocat", "name": "The Octocat", "public_repos": 1}


# --- The guard -------------------------------------------------------------------------


def test_guard_allows_running_job(user) -> None:
    job = make_job(user, "RUNNING")
    with job_write(job.pk):
        pass


@pytest.mark.parametrize("status", ["CANCELLED", "COMPLETED", "FAILED", "PENDING"])
def test_guard_refuses_other_states(user, status: str) -> None:
    job = make_job(user, "RUNNING")
    SyncJob.objects.filter(pk=job.pk).update(status=status)
    with pytest.raises(JobCancelled), job_write(job.pk):
        pytest.fail("the body must not run")


def test_guard_refuses_deleted_job(user) -> None:
    job = make_job(user, "RUNNING")
    job.delete()
    with pytest.raises(JobCancelled), job_write(job.pk):
        pytest.fail("the body must not run")


# --- Profile sync ---------------------------------------------------------------------


def test_sync_step_finishing_after_deletion_writes_nothing(user) -> None:
    job = make_job(user, "RUNNING", steps=initial_steps())
    client = MagicMock()

    def delete_then_answer() -> GitHubUser:
        delete_github_data(user)  # the user deletes their data while the request is in flight
        return GitHubUser.from_api(PROFILE)

    client.get_authenticated_user.side_effect = delete_then_answer
    with pytest.raises(JobCancelled):
        GitHubSyncService(job)._step_profile(client)
    assert not GitHubProfile.objects.filter(user=user).exists()


def test_sync_write_committed_before_deletion_is_deleted(user) -> None:
    job = make_job(user, "RUNNING", steps=initial_steps())
    client = MagicMock()
    client.get_authenticated_user.return_value = GitHubUser.from_api(PROFILE)
    GitHubSyncService(job)._step_profile(client)
    assert GitHubProfile.objects.filter(user=user).exists()

    delete_github_data(user)

    assert not GitHubProfile.objects.filter(user=user).exists()
    with pytest.raises(JobCancelled), job_write(job.pk):
        pass


# --- Profile analysis -------------------------------------------------------------------


def _analyze_after_deletion(user):
    real = profiling.analysis.analyze

    def analyze(*args: Any, **kwargs: Any) -> Any:
        delete_github_data(user)
        return real(*args, **kwargs)

    return patch("services.profiling.analysis.analyze", side_effect=analyze)


def test_analysis_finishing_after_deletion_writes_nothing(synced) -> None:
    job = make_job(synced, "RUNNING", job_type="profile_analysis")
    with _analyze_after_deletion(synced), pytest.raises(JobCancelled):
        ProfileAnalysisService(synced, job_id=job.pk).run()
    assert not DeveloperProfile.objects.filter(user=synced).exists()


def test_analysis_task_ends_quietly_after_deletion(synced) -> None:
    job = make_job(synced, "PENDING", job_type="profile_analysis")
    with _analyze_after_deletion(synced):
        extract_developer_skills.delay(job.pk)
    assert not DeveloperProfile.objects.filter(user=synced).exists()
    assert not SyncJob.objects.filter(pk=job.pk).exists()


def test_analysis_outside_a_job_still_writes(synced) -> None:
    ProfileAnalysisService(synced).run()
    assert DeveloperProfile.objects.filter(user=synced).exists()


# --- Discovery ---------------------------------------------------------------------------


def test_discovery_search_finishing_after_deletion_writes_no_candidates(user, respx_mock) -> None:
    make_developer(user)
    job = new_job(user)
    route = mock_search(respx_mock, {"language:Python": [HTTPX]})

    def delete_then_answer(request: httpx.Request) -> httpx.Response:
        delete_github_data(user)
        return httpx.Response(200, json={"items": [HTTPX]})

    route.mock(side_effect=delete_then_answer)
    with pytest.raises(JobCancelled):
        DiscoveryService(job).run()
    assert not RepositoryCandidate.objects.filter(developer__user=user).exists()
    assert not DeveloperProfile.objects.filter(user=user).exists()
