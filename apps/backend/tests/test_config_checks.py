"""Startup checks for job, sync, GitHub and experience settings (change dev-scripts-checks)."""

import pytest
from django.conf import settings
from django.core.management.base import SystemCheckError
from django.test import override_settings

from core.checks import (
    NON_NEGATIVE_INT_SETTINGS,
    POSITIVE_INT_SETTINGS,
    POSITIVE_NUMBER_SETTINGS,
    profiling_config_check,
    sync_github_config_check,
)
from core.startup import run_startup_checks


def ids(messages) -> list[str]:
    return [m.id for m in messages]


def test_defaults_pass() -> None:
    assert sync_github_config_check() == []
    assert profiling_config_check() == []


@pytest.mark.parametrize("name", POSITIVE_INT_SETTINGS)
@pytest.mark.parametrize("value", [0, -1, "5", 1.5, True])
def test_positive_integers(name: str, value: object) -> None:
    with override_settings(**{name: value}):
        assert ids(sync_github_config_check()) == ["core.E020"]


@pytest.mark.parametrize("name", NON_NEGATIVE_INT_SETTINGS)
def test_non_negative_integers(name: str) -> None:
    with override_settings(**{name: 0}):
        assert sync_github_config_check() == []
    with override_settings(**{name: -1}):
        assert ids(sync_github_config_check()) == ["core.E050"]


@pytest.mark.parametrize("name", POSITIVE_NUMBER_SETTINGS)
@pytest.mark.parametrize("value", [0, -2.5, "10", None])
def test_positive_numbers(name: str, value: object) -> None:
    with override_settings(**{name: value}):
        assert ids(sync_github_config_check()) == ["core.E051"]


def test_positive_number_accepts_int() -> None:
    with override_settings(GITHUB_HTTP_TIMEOUT=3):
        assert sync_github_config_check() == []


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


def test_production_startup_refuses_zero_recovery_interval(settings) -> None:
    settings.RUN_STARTUP_CHECKS = True
    settings.JOB_RECOVERY_INTERVAL_SECONDS = 0
    with pytest.raises(SystemCheckError, match="JOB_RECOVERY_INTERVAL_SECONDS"):
        run_startup_checks()
