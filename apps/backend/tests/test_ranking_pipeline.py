"""Shared ranking stage (Phase 8b, group 1): generation and evaluation rank the same way."""

from collections.abc import Sequence

import pytest
from django.conf import settings
from django.utils import timezone

from developers.models import DeveloperProfile
from e2e.builders import add_candidate
from recommendations.models import Recommendation, ScoringConfig
from services.matching.features import load_candidates, load_developer
from services.matching.issues import IssueFeature, load_issues
from services.ranking.pipeline import rank_pool

from .test_issue_matching import django_issues
from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    generate,
    pool,
    ready_repo,
)

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]


def config(version: str) -> ScoringConfig:
    return ScoringConfig.objects.get(version=version)


def test_issues_loaded_once_for_gated_candidates_only(developer, pool) -> None:
    calls: list[list[int]] = []

    def issues_for(ids: Sequence[int]) -> dict[int, list[IssueFeature]]:
        calls.append(sorted(ids))
        return {}

    v2 = config("v2-deterministic")
    rank_pool(
        load_developer(developer),
        load_candidates(developer),
        v2.weights,
        v2.params,
        issues_for,
        min_score=0.0,
        top_n=50,
    )
    # The Go repository has no skill, language, framework or interest match.
    assert calls == [sorted([pool["django"].pk, pool["plain"].pk])]


def test_no_issue_lookup_without_issue_params(developer, pool) -> None:
    v1 = config("v1-deterministic")

    def issues_for(ids: Sequence[int]) -> dict[int, list[IssueFeature]]:
        raise AssertionError("v1 matches no issues")

    ranked = rank_pool(
        load_developer(developer),
        load_candidates(developer),
        v1.weights,
        v1.params,
        issues_for,
        min_score=0.0,
        top_n=50,
    )
    assert ranked


def test_generation_and_rank_pool_agree(user, developer, pool) -> None:
    DeveloperProfile.objects.filter(pk=developer.pk).update(experience_level="beginner")
    developer.refresh_from_db()
    django_issues(pool["django"])
    generate(user)
    stored = list(
        Recommendation.objects.filter(developer=developer)
        .order_by("rank")
        .values_list("repository_id", "score")
    )

    v2 = config("v2-deterministic")
    now = timezone.now()
    ranked = rank_pool(
        load_developer(developer),
        load_candidates(developer),
        v2.weights,
        v2.params,
        lambda ids: load_issues(ids, now, settings.ISSUE_MAX_AGE_DAYS),
        min_score=settings.RECOMMENDATION_MIN_SCORE,
        top_n=settings.RECOMMENDATIONS_TOP_N,
    )
    assert [(s.repo.id, s.score) for s in ranked] == stored
    assert ranked[0].issues.issues  # issue matching ran


def interest_only(developer):
    repo = ready_repo(4, "other/go-devtool", languages=(("Go", 1000),), topics=("developer-tools",))
    add_candidate(developer, repo, rank=4)
    return repo


def test_relevance_signal_weighted_zero_does_not_pass_the_gate(developer, pool) -> None:
    tool = interest_only(developer)
    v2 = config("v2-deterministic")
    weights = {**v2.weights, "interest": 0.0, "skill": v2.weights["skill"] + v2.weights["interest"]}
    calls: list[list[int]] = []

    def issues_for(ids: Sequence[int]) -> dict[int, list[IssueFeature]]:
        calls.append(sorted(ids))
        return {}

    dev, candidates = load_developer(developer), load_candidates(developer)
    assert next(c for c in candidates if c.id == tool.pk)  # loaded
    ranked = rank_pool(dev, candidates, weights, v2.params, issues_for, min_score=0.0, top_n=50)
    assert tool.pk not in [s.repo.id for s in ranked]
    assert calls == [sorted([pool["django"].pk, pool["plain"].pk])]

    # Under v2 the interest match alone passes the gate, as before.
    calls.clear()
    ranked = rank_pool(dev, candidates, v2.weights, v2.params, issues_for, min_score=0.0, top_n=50)
    assert ranked[[s.repo.id for s in ranked].index(tool.pk)].signals["interest"].value > 0
    assert calls == [sorted([pool["django"].pk, pool["plain"].pk, tool.pk])]
