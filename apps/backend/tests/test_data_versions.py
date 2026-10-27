"""Data versions endpoint (data-versions change)."""

from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import User
from developers.models import DeveloperProfile
from e2e.builders import make_candidate_repo
from feedback.models import SavedRepository
from jobs.models import SyncJob
from repositories.models import Repository
from services.data_versions import versions

from .factories import UserFactory
from .test_models_phase5 import make_recommendation

pytestmark = pytest.mark.django_db

T0 = datetime.fromisoformat("2026-10-27T10:00:00+00:00")
URL = "/api/v1/sync/versions"
Type = SyncJob.JobType


def at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def job(user: User, job_type: str, completed: datetime, status: str = "COMPLETED") -> SyncJob:
    return SyncJob.objects.create(
        user=user, job_type=job_type, status=status, started_at=completed, completed_at=completed
    )


def repo(github_id: int, data_time: datetime) -> Repository:
    """A repository whose every stored data part is from ``data_time``."""
    r = make_candidate_repo(github_id)
    Repository.objects.filter(pk=r.pk).update(
        synced_at=data_time,
        readme_synced_at=data_time,
        community_synced_at=data_time,
        dependencies_synced_at=data_time,
        activity_synced_at=data_time,
        issues_synced_at=data_time,
    )
    return r


@pytest.fixture
def synced(user: User) -> DeveloperProfile:
    """Sync completed at 10:00, profile analyzed at 10:01, generation completed at 10:03, one
    recommended repository with data from 09:30."""
    job(user, Type.GITHUB_PROFILE_SYNC, at(0))
    profile = DeveloperProfile.objects.create(user=user, analyzed_at=at(1))
    job(user, Type.RECOMMENDATION_GENERATION, at(3))
    make_recommendation(profile, repo(1, at(-30)))
    return profile


def body(client: APIClient) -> dict[str, Any]:
    response = client.get(URL)
    assert response.status_code == 200
    return cast(dict[str, Any], response.json())


def test_versions_of_a_synced_user(signed_in_client: APIClient, synced) -> None:
    data = body(signed_in_client)
    assert [datetime.fromisoformat(data[k]) for k in ("github", "profile", "recommendations")] == [
        at(0),
        at(1),
        at(3),
    ]


def test_repository_refreshed_after_the_generation(user, synced) -> None:
    before = versions(user)
    Repository.objects.filter(github_id=1).update(issues_synced_at=at(20))
    after = versions(user)
    assert after.recommendations == at(20)
    assert (after.github, after.profile) == (before.github, before.profile)


def test_analysis_without_a_generation(user, synced) -> None:
    before = versions(user)
    DeveloperProfile.objects.filter(user=user).update(analyzed_at=at(60))
    job(user, Type.REPOSITORY_DISCOVERY, at(61), status="FAILED")
    after = versions(user)
    assert after.profile == at(60)
    assert after.recommendations == before.recommendations


def test_never_synced(signed_in_client: APIClient) -> None:
    assert body(signed_in_client) == {"github": None, "profile": None, "recommendations": None}


def test_another_users_data_is_not_counted(user, synced) -> None:
    other = cast(User, UserFactory())
    other_profile = DeveloperProfile.objects.create(user=other, analyzed_at=at(0))
    elsewhere = repo(2, at(-30))
    make_recommendation(other_profile, elsewhere)
    before = versions(user).recommendations
    Repository.objects.filter(pk=elsewhere.pk).update(issues_synced_at=at(30))
    assert versions(user).recommendations == before
    SavedRepository.objects.create(user=user, repository=elsewhere)
    assert versions(user).recommendations == at(30)


def test_failed_generation_does_not_count(user, synced) -> None:
    job(user, Type.RECOMMENDATION_GENERATION, at(50), status="FAILED")
    assert versions(user).recommendations == at(3)


def test_sync_failed_after_storing_data_counts(user, synced) -> None:
    """A failed sync may already have stored repositories (U-1)."""
    job(user, Type.GITHUB_PROFILE_SYNC, at(31), status="FAILED")
    assert versions(user).github == at(31)


def test_cancelled_sync_does_not_count(user, synced) -> None:
    job(user, Type.GITHUB_PROFILE_SYNC, at(40), status="CANCELLED")
    assert versions(user).github == at(0)


def test_saved_only_repository_counts(user) -> None:
    SavedRepository.objects.create(user=user, repository=repo(3, at(5)))
    assert versions(user).recommendations == at(5)


def test_read_only_and_bounded(signed_in_client: APIClient, user, synced) -> None:
    jobs_before = SyncJob.objects.count()
    repos_before = list(Repository.objects.values().order_by("pk"))
    with CaptureQueriesContext(connection) as queries:
        body(signed_in_client)
    assert SyncJob.objects.count() == jobs_before
    assert list(Repository.objects.values().order_by("pk")) == repos_before
    sql = [q["sql"].lstrip().upper() for q in queries.captured_queries]
    assert not any(s.startswith(("INSERT", "UPDATE", "DELETE")) for s in sql)
    # Session and user, the jobs aggregate, the profile and the repository aggregate.
    assert len(queries.captured_queries) <= 7


def test_requires_authentication(client) -> None:
    response = client.get(URL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
