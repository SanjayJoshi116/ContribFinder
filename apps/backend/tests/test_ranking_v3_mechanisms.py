"""Difficulty fit modes and relevance scaling (ranking-v3-deterministic, group 2)."""

import copy
from typing import Any

import pytest

from services.matching.issues import match_issues
from services.matching.signals import Signal
from services.ranking.config import V2_ISSUE_PARAMS, V2_PARAMS, V2_WEIGHTS, validate
from services.ranking.explain import reasons
from services.ranking.score import contributions

from .test_issue_matching import dev, issue

# Issue score = the confidence of its one technology, so scores are set by the test.
TECH_ONLY = {
    **V2_ISSUE_PARAMS,
    "weights": {"technology": 1.0, "difficulty": 0.0, "approachability": 0.0},
    "min_score": 0.0,
    "saturation": 3.0,
}


def params(mode: str | None) -> dict[str, Any]:
    p = copy.deepcopy(TECH_ONLY)
    if mode:
        p["difficulty_fit_mode"] = mode
    return p


def test_one_weak_fitting_issue() -> None:
    beginner = dev("beginner", django=0.6)
    issues = [issue(1, difficulty="beginner")]
    weighted = match_issues(issues, beginner, params("weighted"))
    assert weighted.issue_fit.value == 0.2
    assert weighted.difficulty_fit.value == 0.2
    assert weighted.difficulty_fit.evidence[0]["mode"] == "weighted"
    assert weighted.difficulty_fit.evidence[0]["best"] == "beginner"
    assert match_issues(issues, beginner, params("best")).difficulty_fit.value == 1.0
    assert match_issues(issues, beginner, params(None)).difficulty_fit.value == 1.0  # default


def test_mixed_difficulties_weighted() -> None:
    intermediate = dev("intermediate", django=0.6, react=0.3)
    issues = [
        issue(1, techs=("django",), difficulty="beginner"),  # table 0.7, score 0.6
        issue(2, techs=("react",), difficulty="intermediate"),  # table 1.0, score 0.3
    ]
    match = match_issues(issues, intermediate, params("weighted"))
    assert match.issue_fit.value == 0.3
    assert match.difficulty_fit.value == 0.24
    assert match.difficulty_fit.evidence[0]["mean"] == 0.8


def test_unknown_difficulties_still_zero_in_weighted_mode() -> None:
    match = match_issues([issue(1, difficulty="unknown")], dev(), params("weighted"))
    assert match.issue_fit.value > 0 and match.difficulty_fit.value == 0


PY = {"name": "Python", "share": 0.9, "confidence": 0.9, "repo_count": 3}
SIGNALS = {
    "skill": Signal(0.8, (PY,)),
    "language": Signal(0.8, (PY,)),
    "interest": Signal(
        0.8, ({"slug": "web", "name": "Web", "strength": 0.8, "via": "topic", "match": "web"},)
    ),
    "framework": Signal(0.8, (PY,)),
    "activity": Signal(1.0, ({"label": "recently_active"},)),
    "openness": Signal(0.5, ({"flag": "contributing"},)),
    "issue_fit": Signal(0.4, ({"count": 2, "by_type": {"code": 2}},)),
    "difficulty_fit": Signal(1.0, ({"best": "beginner", "count": 1, "by_difficulty": {}},)),
}


def with_relevance(value: float) -> dict[str, Signal]:
    return {
        name: Signal(value, s.evidence)
        if name in ("skill", "language", "interest", "framework")
        else s
        for name, s in SIGNALS.items()
    }


def test_relevance_scaling_scales_offer_signals_only() -> None:
    scaled = {**V2_PARAMS, "relevance_scaling": True}
    strong = contributions(with_relevance(0.8), V2_WEIGHTS, scaled)
    weak = contributions(with_relevance(0.3), V2_WEIGHTS, scaled)
    plain = contributions(SIGNALS, V2_WEIGHTS, V2_PARAMS)
    for name in ("activity", "openness", "issue_fit", "difficulty_fit"):
        assert strong[name] == pytest.approx(plain[name] * 0.8)
        assert weak[name] == pytest.approx(plain[name] * 0.3)
    assert strong["skill"] == pytest.approx(0.35 * 0.8)  # relevance signals unscaled


def total(signals: dict[str, Signal], weights: dict[str, float], params: dict[str, Any]) -> float:
    return round(sum(contributions(signals, weights, params).values()), 4)


def test_scaling_off_reproduces_the_weighted_sum() -> None:
    plain = round(sum(V2_WEIGHTS[n] * s.value for n, s in SIGNALS.items()), 4)
    assert total(SIGNALS, V2_WEIGHTS, {}) == plain
    assert total(SIGNALS, V2_WEIGHTS, V2_PARAMS) == plain
    assert total(SIGNALS, V2_WEIGHTS, {**V2_PARAMS, "relevance_scaling": False}) == plain


def test_scaling_with_no_relevance_weight_is_zero() -> None:
    weights = {name: 0.0 for name in V2_WEIGHTS} | {"activity": 1.0}
    assert total(SIGNALS, weights, {"relevance_scaling": True}) == 0.0


def test_reason_weights_follow_scaled_contributions() -> None:
    scaled = {**V2_PARAMS, "relevance_scaling": True}
    signals = with_relevance(0.3)
    expected = contributions(signals, V2_WEIGHTS, scaled)
    found = reasons(signals, expected)
    by_type = {r.type: r.weight for r in found}
    assert by_type["activity"] == round(expected["activity"], 4)
    assert by_type["difficulty"] == round(expected["difficulty_fit"], 4)
    weights = [r.weight for r in found]
    assert weights == sorted(weights, reverse=True)
    # Unscaled, activity (0.10) outranks language (0.15 x 0.3); scaled, it no longer does.
    plain = [r.type for r in reasons(signals, contributions(signals, V2_WEIGHTS, V2_PARAMS))]
    assert plain.index("activity") < plain.index("language")
    assert [r.type for r in found].index("activity") > [r.type for r in found].index("language")


def test_contribution_rounding_to_zero_gives_no_reason() -> None:
    """RNK-7: a reason is stored with its contribution at 4 decimals; 0.0000 is no reason."""
    signals = with_relevance(0.0005)
    parts = contributions(signals, V2_WEIGHTS, {**V2_PARAMS, "relevance_scaling": True})
    assert 0 < parts["openness"] < 0.00005
    found = reasons(signals, parts)
    assert "openness" not in {r.type for r in found}
    assert all(r.weight > 0 for r in found)


def test_validation_of_new_parameters() -> None:
    weighted = copy.deepcopy(V2_PARAMS)
    weighted["issues"]["difficulty_fit_mode"] = "weighted"
    assert validate(V2_WEIGHTS, {**weighted, "relevance_scaling": True}) == []
    bad_mode = copy.deepcopy(V2_PARAMS)
    bad_mode["issues"]["difficulty_fit_mode"] = "average"
    assert validate(V2_WEIGHTS, bad_mode) == [
        "issues.difficulty_fit_mode must be one of best, weighted"
    ]
    assert validate(V2_WEIGHTS, {**V2_PARAMS, "relevance_scaling": "yes"}) == [
        "relevance_scaling must be true or false"
    ]
