"""Core fixes from the review sweep (Bug_Backlog.md batch 27, change core-review-fixes)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.checks import Error
from django.core.management.base import CommandError
from django.test import override_settings

from core.checks import (
    content_security_policy_check,
    discovery_config_check,
    recommendation_config_check,
    sync_github_config_check,
)
from core.logging import redact
from core.reports import write_json
from core.startup import run_startup_checks

from .checks_helpers import ids

# --- Startup gate (CORE-1, CORE-5) ------------------------------------------


def test_a_silenced_error_does_not_block_startup(settings) -> None:
    settings.RUN_STARTUP_CHECKS = True
    error = Error("tolerated", id="core.E099")
    error.is_silenced = lambda: True  # type: ignore[method-assign]
    with patch("core.startup.checks.run_checks", return_value=[error]):
        run_startup_checks()


def test_the_gate_runs_the_deployment_checks(settings) -> None:
    settings.RUN_STARTUP_CHECKS = True
    with patch("core.startup.checks.run_checks", return_value=[]) as run_checks:
        run_startup_checks()
    run_checks.assert_called_once_with(include_deployment_checks=True)


# --- New rules (CORE-2, CORE-4, CORE-6, CORE-8) ------------------------------


@pytest.mark.parametrize("value", [-1, "1", 1.5])
def test_num_proxies_must_be_a_non_negative_integer(value: object) -> None:
    with override_settings(NUM_PROXIES=value):
        assert ids(sync_github_config_check()) == ["core.E050"]


def test_query_shares_need_a_positive_total() -> None:
    shares = dict.fromkeys(settings.DISCOVERY_QUERY_SHARES, 0)
    with override_settings(DISCOVERY_QUERY_SHARES=shares):
        assert ids(discovery_config_check()) == ["core.E022"]


@pytest.mark.parametrize("value", ["default-src 'self'\n", "default-src 'self';\tframe-ancestors"])
def test_a_policy_with_a_control_character_is_refused(value: str) -> None:
    with override_settings(CONTENT_SECURITY_POLICY_HTML=value):
        assert ids(content_security_policy_check()) == ["core.E060"]


def test_a_zero_stale_after_window_is_refused() -> None:
    stale_after = {**settings.REPO_STALE_AFTER, "issues": 0}
    with override_settings(REPO_STALE_AFTER=stale_after):
        assert ids(discovery_config_check()) == ["core.E023"]


# --- Wrongly typed overrides are reported, never a crash (CORE-7) -------------


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DISCOVERY_RESULTS_PER_QUERY", None),
        ("DISCOVERY_MIN_SKILL_CONFIDENCE", "0.5"),
    ],
)
def test_wrongly_typed_discovery_values_are_reported(name: str, value: object) -> None:
    with override_settings(**{name: value}):
        assert ids(discovery_config_check())  # an error, not a TypeError


def test_a_wrongly_typed_minimum_score_is_reported() -> None:
    with override_settings(RECOMMENDATION_MIN_SCORE="0.1"):
        assert "core.E031" in ids(recommendation_config_check())


# --- Redaction (CORE-3) ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("GITHUB_CLIENT_SECRET=abc123def456", "abc123def456"),
        ("encrypted_access_token='gAAAAsecretvalue'", "gAAAAsecretvalue"),
        ("Cookie: sessionid=s3ss10nk3y; csrftoken=csrfv4lue", "s3ss10nk3y"),
        ("Cookie: sessionid=s3ss10nk3y; csrftoken=csrfv4lue", "csrfv4lue"),
        ("password=hunter2", "hunter2"),
        ("TOKEN_ENCRYPTION_KEYS=a3xvsSaVgXP5", "a3xvsSaVgXP5"),
        ('{"client_secret": "shh-its-secret"}', "shh-its-secret"),
    ],
)
def test_redaction_masks_prefixed_names_cookies_and_passwords(text: str, secret: str) -> None:
    assert secret not in redact(text)


def test_redaction_leaves_names_that_only_start_with_a_key() -> None:
    assert redact("statement=kept") == "statement=kept"


# --- Atomic report writes (CORE-9) -------------------------------------------


def test_a_failed_serialization_keeps_the_old_file(tmp_path: Path) -> None:
    out = tmp_path / "benchmark.json"
    out.write_text('{"old": true}\n', encoding="utf-8")
    with pytest.raises(CommandError, match=r"^Benchmark not written to "):
        write_json(out, {"bad": object()}, what="Benchmark")
    assert json.loads(out.read_text(encoding="utf-8")) == {"old": True}


def test_an_interrupted_write_keeps_the_old_file_and_leaves_no_temporary(tmp_path: Path) -> None:
    out = tmp_path / "benchmark.json"
    out.write_text('{"old": true}\n', encoding="utf-8")
    with (
        patch("core.reports.os.replace", side_effect=OSError("disk full")),
        pytest.raises(CommandError, match="disk full"),
    ):
        write_json(out, {"new": True}, what="Benchmark")
    assert json.loads(out.read_text(encoding="utf-8")) == {"old": True}
    assert [p.name for p in tmp_path.iterdir()] == ["benchmark.json"]
