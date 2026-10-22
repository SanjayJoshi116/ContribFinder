import pytest
from django.conf import settings
from django.test import override_settings

from core.checks import profiling_config_check

from .checks_helpers import ids


def test_default_config_is_valid() -> None:
    assert profiling_config_check() == []
    assert settings.EVIDENCE_WEIGHTS["readme"] == 0.20
    assert settings.EVIDENCE_WEIGHTS["repeated_contribution"] == 1.00


@pytest.mark.parametrize(
    "weights",
    [
        {**settings.EVIDENCE_WEIGHTS, "language": 1.5},
        {**settings.EVIDENCE_WEIGHTS, "language": -0.1},
        {**settings.EVIDENCE_WEIGHTS, "language": "high"},
        {k: v for k, v in settings.EVIDENCE_WEIGHTS.items() if k != "topic"},
        {**settings.EVIDENCE_WEIGHTS, "stars": 0.5},
    ],
    ids=["above-one", "negative", "not-a-number", "missing", "unknown"],
)
def test_invalid_evidence_weights_rejected(weights) -> None:
    with override_settings(EVIDENCE_WEIGHTS=weights):
        assert "core.E010" in ids(profiling_config_check())


def test_invalid_interest_weights_rejected() -> None:
    with override_settings(
        INTEREST_EVIDENCE_WEIGHTS={**settings.INTEREST_EVIDENCE_WEIGHTS, "topic": 2}
    ):
        assert "core.E011" in ids(profiling_config_check())


@pytest.mark.parametrize("name", ["EVIDENCE_REPEAT_DECAY", "CONFIDENCE_CAP"])
@pytest.mark.parametrize("value", [0, 1, 1.2])
def test_decay_and_cap_must_be_open_interval(name: str, value: float) -> None:
    with override_settings(**{name: value}):
        assert "core.E012" in ids(profiling_config_check())


# --- EXPERIENCE_THRESHOLDS (change dev-scripts-checks) -----------------------------------


@pytest.mark.parametrize(
    "change",
    [
        {"account_age_years": 3},
        {"account_age_years": [1]},
        {"account_age_years": [1, 2, 3]},
        {"account_age_years": [4, 1]},
        {"account_age_years": [-1, 2]},
        {"account_age_years": ["1", 2]},
        {"stars": [1, 2]},
    ],
    ids=["scalar", "one", "three", "reversed", "negative", "string", "unknown-signal"],
)
def test_experience_thresholds(change: dict[str, object]) -> None:
    with override_settings(EXPERIENCE_THRESHOLDS={**settings.EXPERIENCE_THRESHOLDS, **change}):
        assert "core.E014" in ids(profiling_config_check())


def test_experience_thresholds_missing_signal() -> None:
    thresholds = dict(settings.EXPERIENCE_THRESHOLDS)
    del thresholds["account_age_years"]
    with override_settings(EXPERIENCE_THRESHOLDS=thresholds):
        assert "core.E014" in ids(profiling_config_check())


def test_experience_thresholds_equal_pair_allowed() -> None:
    change = {"account_age_years": [2, 2.0]}
    with override_settings(EXPERIENCE_THRESHOLDS={**settings.EXPERIENCE_THRESHOLDS, **change}):
        assert profiling_config_check() == []
