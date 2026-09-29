import pytest
from django.conf import settings
from django.test import override_settings

from core.checks import profiling_config_check


def ids(messages) -> list[str]:
    return [m.id for m in messages]


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
