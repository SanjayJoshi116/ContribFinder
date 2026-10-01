"""Loading matching inputs from the database (Phase 5, group 3)."""

from datetime import timedelta
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from developers.models import DeveloperProfile, DeveloperSkill, Skill, SkillEvidence
from repositories.models import RepositoryLanguage, RepositorySnapshot, RepositoryTopic
from services.matching.features import load_candidates, load_developer

from .repo_fixtures import add_candidate, make_candidate_repo

pytestmark = pytest.mark.django_db


@pytest.fixture
def profile(user) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


def ready_repo(github_id: int, **fields: Any):
    return make_candidate_repo(github_id, lifecycle="recommendable", is_eligible=True, **fields)


def test_only_eligible_recommendable_candidates(profile) -> None:
    good = ready_repo(1, full_name="a/good")
    variants: list[dict[str, Any]] = [
        {"lifecycle": "indexed", "is_eligible": False},
        {"lifecycle": "failed", "is_eligible": False},
        {"lifecycle": "discovered"},
        {"lifecycle": "fetching"},
    ]
    for i, fields in enumerate(variants, start=2):
        add_candidate(profile, make_candidate_repo(i, **fields))
    add_candidate(profile, good, rank=7)
    add_candidate(profile, good, source="topic_search", query="topic:cli", rank=3)
    loaded = load_candidates(profile)
    assert [r.full_name for r in loaded] == ["a/good"]
    assert loaded[0].best_search_rank == 3


def test_latest_snapshot_languages_and_topics(profile) -> None:
    repo = ready_repo(1, has_contributing=True)
    RepositoryLanguage.objects.create(repository=repo, language="Python", bytes=900)
    RepositoryTopic.objects.create(repository=repo, topic="django")
    for label, age in (("low_activity", 5), ("recently_active", 1)):
        RepositorySnapshot.objects.create(
            repository=repo,
            captured_at=timezone.now() - timedelta(days=age),
            stars=1,
            forks=0,
            open_issues=0,
            activity_label=label,
            thresholds_version="x",
            contributors=12,
        )
    add_candidate(profile, repo)
    [data] = load_candidates(profile)
    assert data.languages == (("Python", 900),)
    assert data.topics == ("django",)
    assert data.has_contributing is True
    assert data.snapshot is not None and data.snapshot.activity_label == "recently_active"


def test_query_count_does_not_grow(profile) -> None:
    def count() -> int:
        with CaptureQueriesContext(connection) as ctx:
            load_candidates(profile)
        return len(ctx)

    add_candidate(profile, ready_repo(1))
    few = count()
    for i in range(2, 12):
        r = ready_repo(i)
        RepositoryTopic.objects.create(repository=r, topic="cli")
        add_candidate(profile, r)
    assert count() == few


def test_developer_features(profile) -> None:
    skill = Skill.objects.create(slug="python", name="Python", category="language")
    ds = DeveloperSkill.objects.create(profile=profile, skill=skill, confidence=0.9)
    for i in (1, 2):
        SkillEvidence.objects.create(
            developer_skill=ds, source="language", repository=make_candidate_repo(i)
        )
    SkillEvidence.objects.create(developer_skill=ds, source="readme")
    features = load_developer(profile)
    assert features.skills["python"].confidence == 0.9
    assert features.skills["python"].repo_count == 2
    assert features.confidence("rust") == 0.0
