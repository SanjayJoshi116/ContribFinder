"""Loading matching inputs from the database (Phase 5, group 3)."""

from datetime import timedelta
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from developers.models import DeveloperProfile, DeveloperSkill, Skill, SkillEvidence
from e2e.builders import add_candidate, make_candidate_repo
from repositories.models import RepositoryLanguage, RepositorySnapshot, RepositoryTopic
from services.matching.features import load_candidates, load_developer

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
            commits_90d=42 if label == "recently_active" else 0,
        )
    add_candidate(profile, repo)
    [data] = load_candidates(profile)
    assert data.languages == (("Python", 900),)
    assert data.topics == ("django",)
    assert data.has_contributing is True
    assert data.snapshot is not None and data.snapshot.activity_label == "recently_active"


def snapshot_of(repo, captured_at, **fields: Any) -> RepositorySnapshot:
    return RepositorySnapshot.objects.create(
        **{
            "repository": repo,
            "captured_at": captured_at,
            "stars": 1,
            "forks": 0,
            "open_issues": 0,
            "days_since_push": 0,
            "commits_90d": 42,
            "prs_merged_90d": 9,
            "activity_label": "recently_active",
            "thresholds_version": "x",
            **fields,
        }
    )


def test_activity_measured_at_load(profile) -> None:
    now = timezone.now()
    captured = now - timedelta(days=40)
    repo = ready_repo(1, pushed_at=captured)  # refresh kept failing since
    stored = snapshot_of(repo, captured)
    add_candidate(profile, repo)
    [data] = load_candidates(profile, now=now)
    assert data.snapshot is not None
    assert (data.snapshot.days_since_push, data.snapshot.activity_label) == (
        40,
        "moderately_active",
    )
    stored.refresh_from_db()
    assert (stored.days_since_push, stored.activity_label) == (0, "recently_active")


def test_threshold_change_applies_before_a_refresh(profile, settings) -> None:
    now = timezone.now()
    repo = ready_repo(1, pushed_at=now - timedelta(days=3))
    snapshot_of(repo, now - timedelta(hours=1), days_since_push=3)
    add_candidate(profile, repo)
    settings.ACTIVITY_THRESHOLDS = {
        **settings.ACTIVITY_THRESHOLDS,
        "recent_commits": 50,
        "recent_merged_prs": 50,
    }
    [data] = load_candidates(profile, now=now)
    assert data.snapshot is not None and data.snapshot.activity_label == "moderately_active"
    assert RepositorySnapshot.objects.get().activity_label == "recently_active"


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


def test_repository_count_is_own_repositories_only(profile) -> None:
    skill = Skill.objects.create(slug="django", name="Django", category="framework")
    ds = DeveloperSkill.objects.create(profile=profile, skill=skill, confidence=0.8)
    SkillEvidence.objects.create(
        developer_skill=ds, source="dependency", repository=make_candidate_repo(1)
    )
    for i, source in ((2, "pull_request"), (3, "repeated_contribution")):
        SkillEvidence.objects.create(
            developer_skill=ds, source=source, repository=make_candidate_repo(i)
        )
    assert load_developer(profile).skills["django"].repo_count == 1


def test_sql_activity_matches_python(settings) -> None:
    """`repositories.queries.with_current_activity` (discovery list) and
    `features.current_activity` (generation, saved list, detail) agree (CR5-2)."""
    from itertools import product

    from repositories.queries import with_current_activity
    from services.matching.features import current_activity

    now = timezone.now()
    thresholds = settings.ACTIVITY_THRESHOLDS
    pushes = [None, now - timedelta(days=3), now - timedelta(days=40, hours=12)]
    rows = []
    for i, pushed_at in enumerate(pushes, start=1):
        repo = ready_repo(i, pushed_at=pushed_at)
        for days, captured, commits, merged in product(
            (None, 0, 5),
            (now - timedelta(hours=1), now - timedelta(days=7, hours=12), now - timedelta(days=95)),
            (None, 0, 42),
            (None, 0, 9),
        ):
            rows.append(
                RepositorySnapshot(
                    repository=repo,
                    captured_at=captured,
                    stars=1,
                    forks=0,
                    open_issues=0,
                    days_since_push=days,
                    commits_90d=commits,
                    prs_merged_90d=merged,
                    activity_label="low_activity",
                    thresholds_version="x",
                )
            )
    RepositorySnapshot.objects.bulk_create(rows)
    annotated = with_current_activity(
        RepositorySnapshot.objects.select_related("repository"), now, thresholds
    )
    for snapshot in annotated:
        expected = current_activity(snapshot, snapshot.repository.pushed_at, now, thresholds)
        got = (snapshot.current_days, snapshot.current_label)  # type: ignore[attr-defined]
        assert got == expected, snapshot.pk
