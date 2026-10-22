"""Startup checks for job, sync and GitHub settings (change dev-scripts-checks)."""

import pytest
from django.core.management.base import SystemCheckError
from django.test import override_settings

from core.checks import (
    NON_NEGATIVE_INT_SETTINGS,
    POSITIVE_INT_SETTINGS,
    POSITIVE_NUMBER_SETTINGS,
    sync_github_config_check,
)
from core.startup import run_startup_checks

from .checks_helpers import ids


def test_defaults_pass() -> None:
    assert sync_github_config_check() == []


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


def test_production_startup_refuses_zero_recovery_interval(settings) -> None:
    settings.RUN_STARTUP_CHECKS = True
    settings.JOB_RECOVERY_INTERVAL_SECONDS = 0
    with pytest.raises(SystemCheckError, match="JOB_RECOVERY_INTERVAL_SECONDS"):
        run_startup_checks()
