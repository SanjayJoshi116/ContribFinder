"""Scoring configuration validation and recommendation settings check (Phase 5, group 2)."""

import copy

import pytest
from django.test import override_settings

from core.checks import recommendation_config_check
from services.ranking.config import V1_PARAMS, V1_WEIGHTS, validate


def ids(messages) -> list[str]:
    return [m.id for m in messages]


def test_v1_is_valid() -> None:
    assert validate(V1_WEIGHTS, V1_PARAMS) == []


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ({k: v for k, v in V1_WEIGHTS.items() if k != "openness"}, "exactly the signals"),
        ({**V1_WEIGHTS, "semantic": 0.0}, "exactly the signals"),
        ({**V1_WEIGHTS, "skill": 0.50, "language": -0.05}, "non-negative"),
        ({**V1_WEIGHTS, "skill": 0.30}, "sum to 1"),
        ({**V1_WEIGHTS, "skill": True}, "non-negative"),
    ],
    ids=["missing", "unknown", "negative", "sum", "bool"],
)
def test_invalid_weights(weights, message: str) -> None:
    assert any(message in e for e in validate(weights, V1_PARAMS))


def _params(**changes):
    params = copy.deepcopy(V1_PARAMS)
    for path, value in changes.items():
        section, key = path.split("__")
        params[section][key] = value
    return params


@pytest.mark.parametrize(
    ("params", "message"),
    [
        (_params(bands__good=0.6), "lower than bands.strong"),
        (_params(bands__strong=1.5), "between 0 and 1"),
        (_params(activity__recently_active=-0.1), "between 0 and 1"),
        ({**V1_PARAMS, "openness": {"contributing": 0.4}}, "exactly the keys"),
        ({k: v for k, v in V1_PARAMS.items() if k != "tech_sources"}, "tech_sources"),
    ],
    ids=["bands-order", "band-range", "activity-range", "openness-keys", "missing-section"],
)
def test_invalid_params(params, message: str) -> None:
    assert any(message in e for e in validate(V1_WEIGHTS, params))


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
