import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from developers.models import (
    DeveloperInterest,
    DeveloperProfile,
    DeveloperSkill,
    Interest,
    InterestEvidence,
    Skill,
    SkillEvidence,
)
from jobs.models import SyncJob
from repositories.models import RepositoryDependency, UserRepository

from .test_models_phase2 import make_repo

pytestmark = pytest.mark.django_db


@pytest.fixture
def profile(user) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


@pytest.fixture
def python() -> Skill:
    return Skill.objects.create(slug="python", name="Python", category="language")


def test_profile_defaults(profile) -> None:
    assert profile.experience_level == "unknown"
    assert profile.preferred_project_size == "any"
    assert profile.preferred_issue_difficulty == "unknown"


def test_skill_unique_per_profile(profile, python) -> None:
    DeveloperSkill.objects.create(profile=profile, skill=python, confidence=0.5)
    with pytest.raises(IntegrityError), transaction.atomic():
        DeveloperSkill.objects.create(profile=profile, skill=python, confidence=0.7)


def test_interest_unique_per_profile(profile) -> None:
    ai = Interest.objects.create(slug="ai", name="AI")
    DeveloperInterest.objects.create(profile=profile, interest=ai, strength=0.5)
    with pytest.raises(IntegrityError), transaction.atomic():
        DeveloperInterest.objects.create(profile=profile, interest=ai, strength=0.6)


def test_dependency_unique_per_repository_and_ecosystem() -> None:
    repo = make_repo()
    RepositoryDependency.objects.create(
        repository=repo, ecosystem="pypi", name="django", manifest_path="pyproject.toml"
    )
    # Same name in another ecosystem is a different dependency.
    RepositoryDependency.objects.create(
        repository=repo, ecosystem="npm", name="django", manifest_path="package.json"
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        RepositoryDependency.objects.create(
            repository=repo, ecosystem="pypi", name="django", manifest_path="requirements.txt"
        )


def test_owner_and_contributor_links_coexist(user) -> None:
    repo = make_repo()
    UserRepository.objects.create(user=user, repository=repo, relation="owner")
    UserRepository.objects.create(
        user=user, repository=repo, relation="contributor", merged_pr_count=2, push_count=1
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        UserRepository.objects.create(user=user, repository=repo, relation="contributor")


def test_profile_delete_cascades(profile, python) -> None:
    ds = DeveloperSkill.objects.create(profile=profile, skill=python, confidence=0.5)
    SkillEvidence.objects.create(developer_skill=ds, source="readme")
    ai = Interest.objects.create(slug="ai", name="AI")
    di = DeveloperInterest.objects.create(profile=profile, interest=ai, strength=0.5)
    InterestEvidence.objects.create(developer_interest=di, source="topic")
    profile.delete()
    assert not DeveloperSkill.objects.exists()
    assert not SkillEvidence.objects.exists()
    assert not InterestEvidence.objects.exists()
    # Catalog rows survive.
    assert Skill.objects.exists() and Interest.objects.exists()


def test_evidence_keeps_row_when_repository_deleted(profile, python) -> None:
    repo = make_repo()
    ds = DeveloperSkill.objects.create(profile=profile, skill=python, confidence=0.5)
    evidence = SkillEvidence.objects.create(developer_skill=ds, source="language", repository=repo)
    repo.delete()
    evidence.refresh_from_db()
    assert evidence.repository is None


def test_analysis_job_has_its_own_active_slot(user) -> None:
    SyncJob.objects.create(user=user, job_type="github_profile_sync", status="RUNNING")
    SyncJob.objects.create(user=user, job_type="profile_analysis", status="PENDING")
    with pytest.raises(IntegrityError), transaction.atomic():
        SyncJob.objects.create(user=user, job_type="profile_analysis", status="PENDING")
