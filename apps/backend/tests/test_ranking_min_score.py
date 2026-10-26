"""Minimum score in the scoring configuration (ranking-min-score-config, group 2)."""

import copy
from typing import Any

import pytest

from recommendations.models import Recommendation, ScoringConfig
from services.matching.features import RepoData, load_candidates, load_developer
from services.matching.signals import Signal
from services.ranking.config import V2_PARAMS, V2_WEIGHTS, validate
from services.ranking.pipeline import rank_pool
from services.ranking.score import Scored, rank

from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    generate,
    pool,
)


def repo(name: str) -> RepoData:
    return RepoData(1, name, "", (), (), (), False, False, False, False, None, None)


def scored(name: str, score: float, relevance: float) -> Scored:
    signals = {"skill": Signal(0.5), "language": Signal(0), "framework": Signal(0)}
    signals["interest"] = Signal(0)
    return Scored(repo(name), {}, signals, score, "partial", relevance=relevance, relevant=True)


def names(kept: list[Scored]) -> list[str]:
    return [s.repo.full_name for s in kept]


def test_relevance_basis_keeps_and_drops() -> None:
    both = [scored("thin", 0.20, 0.08), scored("solid", 0.15, 0.12)]
    assert names(rank(both, min_score=0.10, top_n=50, basis="relevance")) == ["solid"]
    assert names(rank(both, min_score=0.10, top_n=50)) == ["thin", "solid"]  # score basis


@pytest.mark.django_db
@pytest.mark.respx(assert_all_called=False)
def test_config_minimum_wins_over_installation_value(developer, pool) -> None:
    dev, candidates = load_developer(developer), load_candidates(developer)

    def run(params: dict[str, Any]) -> list[str]:
        ranked = rank_pool(
            dev, candidates, V2_WEIGHTS, params, lambda ids: {}, min_score=0.10, top_n=50
        )
        return [s.repo.full_name for s in ranked]

    default = run(V2_PARAMS)
    assert run({**V2_PARAMS, "min_score": 0.95}) == []  # the configuration's value wins
    assert run({**V2_PARAMS, "min_score": 0.0}) == default  # nothing below 0.10 was relevant
    assert run({**V2_PARAMS, "min_score": 0.10, "min_score_basis": "score"}) == default


def test_validation() -> None:
    def errors(**extra: Any) -> list[str]:
        return validate(V2_WEIGHTS, {**copy.deepcopy(V2_PARAMS), **extra})

    assert errors(min_score=0.05, min_score_basis="relevance") == []
    assert errors(min_score=1.5) == ["min_score must be a number between 0 and 1"]
    assert errors(min_score=0.1, min_score_basis="issues") == [
        "min_score_basis must be one of score, relevance"
    ]
    assert errors(min_score_basis="score") == ["min_score_basis requires min_score"]


@pytest.mark.django_db
@pytest.mark.respx(assert_all_called=False)
def test_generation_uses_the_configuration_minimum(user, developer, pool) -> None:
    generate(user)
    assert Recommendation.objects.filter(developer=developer).exists()
    v2 = ScoringConfig.objects.get(version="v2-deterministic")
    ScoringConfig.objects.filter(is_active=True).update(is_active=False)
    ScoringConfig.objects.create(
        version="strict",
        weights=v2.weights,
        params={**v2.params, "min_score": 0.95},
        is_active=True,
    )
    generate(user)
    assert not Recommendation.objects.filter(developer=developer).exists()
