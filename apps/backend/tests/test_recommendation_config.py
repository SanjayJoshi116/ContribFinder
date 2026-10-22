"""Scoring configuration validation and recommendation settings check (Phase 5, group 2)."""

import copy

import pytest
from django.test import override_settings

from core.checks import recommendation_config_check
from services.ranking.config import V1_PARAMS, V1_WEIGHTS, V2_PARAMS, V2_WEIGHTS, validate

from .checks_helpers import ids


def test_v2_is_valid() -> None:
    assert validate(V2_WEIGHTS, V2_PARAMS) == []


def test_v1_is_valid_only_as_a_stored_config() -> None:
    assert validate(V1_WEIGHTS, V1_PARAMS, stored=True) == []
    assert any("exactly the signals" in e for e in validate(V1_WEIGHTS, V1_PARAMS))


def test_stored_config_with_issue_weights_needs_issue_params() -> None:
    assert any(
        "issues must be an object" in e for e in validate(V2_WEIGHTS, V1_PARAMS, stored=True)
    )


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ({k: v for k, v in V2_WEIGHTS.items() if k != "openness"}, "exactly the signals"),
        ({k: v for k, v in V2_WEIGHTS.items() if k != "issue_fit"}, "exactly the signals"),
        ({**V2_WEIGHTS, "semantic": 0.0}, "exactly the signals"),
        ({**V2_WEIGHTS, "skill": 0.50, "language": -0.05}, "non-negative"),
        ({**V2_WEIGHTS, "skill": 0.30}, "sum to 1"),
        ({**V2_WEIGHTS, "skill": True}, "non-negative"),
    ],
    ids=["missing", "missing-issue-signal", "unknown", "negative", "sum", "bool"],
)
def test_invalid_weights(weights, message: str) -> None:
    assert any(message in e for e in validate(weights, V2_PARAMS))


def _params(**changes):
    params = copy.deepcopy(V2_PARAMS)
    for path, value in changes.items():
        *sections, key = path.split("__")
        target = params
        for section in sections:
            target = target[section]
        target[key] = value
    return params


@pytest.mark.parametrize(
    ("params", "message"),
    [
        (_params(bands__good=0.6), "lower than bands.strong"),
        (_params(bands__strong=1.5), "between 0 and 1"),
        (_params(activity__recently_active=-0.1), "between 0 and 1"),
        ({**V2_PARAMS, "openness": {"contributing": 0.4}}, "exactly the keys"),
        ({k: v for k, v in V2_PARAMS.items() if k != "tech_sources"}, "tech_sources"),
        ({k: v for k, v in V2_PARAMS.items() if k != "issues"}, "issues must be an object"),
        (_params(issues__weights__technology=0.7), "issues.weights must sum to 1"),
        (_params(issues__min_score=1.2), "issues.min_score"),
        (_params(issues__per_recommendation=0), "issues.per_recommendation"),
        (_params(issues__per_recommendation=2.5), "issues.per_recommendation"),
        (_params(issues__saturation=0), "issues.saturation"),
        (_params(issues__approachability__help_wanted=2), "issues.approachability.help_wanted"),
        (
            _params(issues__difficulty_fit={"beginner": {}}),
            "issues.difficulty_fit must have exactly the rows",
        ),
        (
            _params(issues__difficulty_fit__experienced__advanced=1.5),
            "issues.difficulty_fit.experienced.advanced",
        ),
        (
            _params(issues__difficulty_fit__unknown={"beginner": 0.5}),
            "issues.difficulty_fit.unknown must have exactly the keys",
        ),
    ],
    ids=[
        "bands-order",
        "band-range",
        "activity-range",
        "openness-keys",
        "missing-section",
        "missing-issues",
        "issue-weights-sum",
        "min-score-range",
        "per-recommendation-zero",
        "per-recommendation-float",
        "saturation",
        "approachability-range",
        "table-rows",
        "table-value",
        "table-columns",
    ],
)
def test_invalid_params(params, message: str) -> None:
    assert any(message in e for e in validate(V2_WEIGHTS, params))


def test_default_settings_are_valid() -> None:
    assert recommendation_config_check() == []


@pytest.mark.parametrize("value", [19, 0, "50"])
def test_top_n_at_least_20(value) -> None:
    with override_settings(RECOMMENDATIONS_TOP_N=value):
        assert "core.E030" in ids(recommendation_config_check())


def test_min_score_range() -> None:
    with override_settings(RECOMMENDATION_MIN_SCORE=1.5):
        assert "core.E031" in ids(recommendation_config_check())


@pytest.mark.parametrize(
    "sizes",
    [{"small": 100, "medium": 10}, {"small": 0, "medium": 10}, {"small": 10}],
    ids=["order", "zero", "missing"],
)
def test_size_thresholds(sizes) -> None:
    with override_settings(REPO_SIZE_THRESHOLDS=sizes):
        assert "core.E032" in ids(recommendation_config_check())
