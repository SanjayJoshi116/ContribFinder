"""Startup validation for production processes (change security-hardening)."""

from unittest.mock import patch

import pytest
from django.core.checks import Error, Warning
from django.core.management.base import SystemCheckError

from config.celery import _check_configuration
from core.startup import run_startup_checks


def test_inactive_unless_enabled(settings) -> None:
    settings.RUN_STARTUP_CHECKS = False
    settings.TOKEN_ENCRYPTION_KEYS = []
    run_startup_checks()  # does nothing


def test_valid_configuration_passes(settings) -> None:
    settings.RUN_STARTUP_CHECKS = True
    run_startup_checks()


def test_invalid_configuration_refuses_to_start(settings) -> None:
    settings.RUN_STARTUP_CHECKS = True
    canned = [Error("keys missing", id="core.E001"), Warning("minor", id="core.W002")]
    with (
        patch("core.startup.checks.run_checks", return_value=canned),
        pytest.raises(SystemCheckError, match=r"core\.E001") as raised,
    ):
        run_startup_checks()
    assert "core.W002" not in str(raised.value)


def test_warnings_are_logged_not_fatal(settings, caplog: pytest.LogCaptureFixture) -> None:
    settings.RUN_STARTUP_CHECKS = True
    canned = [Warning("proxy", id="core.W002")]
    with patch("core.startup.checks.run_checks", return_value=canned):
        run_startup_checks()
    assert "core.W002" in caplog.text


def test_worker_and_beat_init_run_the_checks() -> None:
    with patch("core.startup.run_startup_checks") as checks:
        _check_configuration(sender=None)
    checks.assert_called_once_with()
