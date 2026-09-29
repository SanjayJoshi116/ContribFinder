import importlib

import pytest
from django.db import IntegrityError, migrations, transaction
from django.utils import timezone

from developers.models import DeveloperProfile
from repositories.models import (
    CandidateDiscovery,
    Repository,
    RepositoryCandidate,
    RepositoryReadme,
    RepositorySnapshot,
)

from .test_models_phase2 import make_repo

pytestmark = pytest.mark.django_db


@pytest.fixture
def profile(user) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


def candidate(profile: DeveloperProfile, repo: Repository) -> RepositoryCandidate:
    now = timezone.now()
    return RepositoryCandidate.objects.create(
        developer=profile, repository=repo, first_discovered_at=now, last_seen_at=now
    )


def discovery(cand: RepositoryCandidate, source: str, query: str = "") -> CandidateDiscovery:
    now = timezone.now()
    return CandidateDiscovery.objects.create(
        candidate=cand, source=source, query=query, first_seen_at=now, last_seen_at=now
    )


def snapshot(repo: Repository, **kw) -> RepositorySnapshot:
    defaults = {
        "captured_at": timezone.now(),
        "stars": 1,
        "forks": 0,
        "open_issues": 0,
        "activity_label": "low_activity",
        "thresholds_version": "x",
    }
    return RepositorySnapshot.objects.create(repository=repo, **{**defaults, **kw})


def test_new_repository_defaults() -> None:
    repo = make_repo()
    assert repo.lifecycle == "discovered"
    assert repo.is_eligible is None
    assert repo.has_contributing is None
    assert repo.stale_parts == []


def test_one_candidate_per_developer_and_repository(profile) -> None:
    repo = make_repo()
    candidate(profile, repo)
    with pytest.raises(IntegrityError), transaction.atomic():
        candidate(profile, repo)


def test_discovery_unique_per_source_and_query(profile) -> None:
    cand = candidate(profile, make_repo())
    discovery(cand, "language_search", "language:Python")
    discovery(cand, "interest_search", "topic:cli")  # another source is fine
    with pytest.raises(IntegrityError), transaction.atomic():
        discovery(cand, "language_search", "language:Python")


def test_candidates_cascade_with_profile_but_repository_is_kept(profile) -> None:
    repo = make_repo()
    discovery(candidate(profile, repo), "previously_interacted")
    profile.delete()
    assert not RepositoryCandidate.objects.exists()
    assert not CandidateDiscovery.objects.exists()
    assert Repository.objects.filter(pk=repo.pk).exists()


def test_deleting_candidate_keeps_repository(profile) -> None:
    repo = make_repo()
    candidate(profile, repo).delete()
    assert Repository.objects.filter(pk=repo.pk).exists()


def test_readme_and_snapshots_cascade_with_repository(profile) -> None:
    repo = make_repo()
    RepositoryReadme.objects.create(
        repository=repo, content="# hi", size=4, fetched_at=timezone.now()
    )
    snapshot(repo)
    candidate(profile, repo)
    repo.delete()
    assert not RepositoryReadme.objects.exists()
    assert not RepositorySnapshot.objects.exists()
    assert not RepositoryCandidate.objects.exists()


def test_existing_repositories_migrate_to_discovered() -> None:
    migration = importlib.import_module(
        "repositories.migrations.0003_discovery_lifecycle_and_candidates"
    ).Migration
    added = {
        op.name: op.field
        for op in migration.operations
        if isinstance(op, migrations.AddField) and op.model_name == "repository"
    }
    assert added["lifecycle"].default == "discovered"
    # Every other new column is nullable or has a default: no data change for existing rows.
    for name, field in added.items():
        assert field.null or field.has_default() or field.blank, name
