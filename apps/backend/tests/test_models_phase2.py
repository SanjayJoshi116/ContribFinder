from typing import cast

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from jobs.models import SyncJob
from repositories.models import Repository, RepositoryLanguage, RepositoryTopic

pytestmark = pytest.mark.django_db

SYNC = SyncJob.JobType.GITHUB_PROFILE_SYNC


def make_repo(github_id: int = 1) -> Repository:
    return Repository.objects.create(
        github_id=github_id,
        owner_login="octocat",
        name=f"repo{github_id}",
        full_name=f"octocat/repo{github_id}",
        html_url=f"https://github.com/octocat/repo{github_id}",
        synced_at=timezone.now(),
    )


@pytest.mark.parametrize("active", ["PENDING", "RUNNING", "RETRYING"])
def test_second_active_job_rejected(user, active: str) -> None:
    SyncJob.objects.create(user=user, job_type=SYNC, status=active)
    with pytest.raises(IntegrityError), transaction.atomic():
        SyncJob.objects.create(user=user, job_type=SYNC, status="PENDING")


@pytest.mark.parametrize("terminal", ["COMPLETED", "FAILED", "CANCELLED"])
def test_new_job_allowed_after_terminal(user, terminal: str) -> None:
    SyncJob.objects.create(user=user, job_type=SYNC, status=terminal)
    SyncJob.objects.create(user=user, job_type=SYNC, status="PENDING")
    assert SyncJob.objects.filter(user=user).count() == 2


def test_active_jobs_of_different_users_coexist(user) -> None:
    from .factories import UserFactory

    other = cast(User, UserFactory())
    SyncJob.objects.create(user=user, job_type=SYNC, status="RUNNING")
    SyncJob.objects.create(user=other, job_type=SYNC, status="RUNNING")
    assert SyncJob.objects.filter(status="RUNNING").count() == 2


def test_language_pair_unique() -> None:
    repo = make_repo()
    RepositoryLanguage.objects.create(repository=repo, language="Python", bytes=10)
    with pytest.raises(IntegrityError), transaction.atomic():
        RepositoryLanguage.objects.create(repository=repo, language="Python", bytes=20)


def test_topic_pair_unique() -> None:
    repo = make_repo()
    RepositoryTopic.objects.create(repository=repo, topic="django")
    with pytest.raises(IntegrityError), transaction.atomic():
        RepositoryTopic.objects.create(repository=repo, topic="django")
