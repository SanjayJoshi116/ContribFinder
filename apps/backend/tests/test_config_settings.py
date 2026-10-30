"""Settings helpers and settings-level behavior (Bug_Backlog.md batch 26, CFG-1...CFG-10)."""

import os
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework import exceptions

from config.exceptions import api_exception_handler
from config.settings.base import env_json, env_mapping, env_words


def test_env_mapping_merges_an_object_over_the_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CF_TEST_MAPPING", '{"b": 3}')
    assert env_mapping("CF_TEST_MAPPING", {"a": 1, "b": 2}) == {"a": 1, "b": 3}


def test_env_mapping_without_a_value_returns_a_copy_of_the_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CF_TEST_MAPPING", raising=False)
    defaults = {"a": 1}
    result = env_mapping("CF_TEST_MAPPING", defaults)
    assert result == defaults
    assert result is not defaults


@pytest.mark.parametrize("raw", ["[1, 4]", '"x"', "not json", "3"])
def test_env_mapping_refuses_anything_but_an_object_naming_the_setting(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("CF_TEST_MAPPING", raw)
    with pytest.raises(
        ImproperlyConfigured, match=r"CF_TEST_MAPPING (must be a JSON object|is not valid JSON)"
    ):
        env_mapping("CF_TEST_MAPPING", {"a": 1})


@pytest.mark.parametrize(
    ("raw", "words"),
    [
        ("", []),
        ("read:user", ["read:user"]),
        ("read:user user:email", ["read:user", "user:email"]),
        ("read:user,user:email", ["read:user", "user:email"]),
        (" read:user, user:email ", ["read:user", "user:email"]),
    ],
)
def test_env_words_splits_on_spaces_and_commas(
    monkeypatch: pytest.MonkeyPatch, raw: str, words: list[str]
) -> None:
    monkeypatch.setenv("CF_TEST_WORDS", raw)
    assert env_words("CF_TEST_WORDS") == words


def test_a_structured_detail_goes_to_details_not_into_the_message() -> None:
    response = api_exception_handler(exceptions.NotFound({"repository": "gone"}), {})
    error = response.data["error"]
    assert error["code"] == "not_found"
    assert error["message"] == "Not found."
    assert error["details"] == {"repository": "gone"}


def test_only_database_url_is_taken_from_the_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from config.settings.base import _dotenv_value

    dotenv = tmp_path / ".env"
    dotenv.write_text("export REDIS_URL=redis://x:6379/1\nDATABASE_URL='postgres://u:p@h/db'\n")
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert _dotenv_value(dotenv, "DATABASE_URL") == "postgres://u:p@h/db"
    assert _dotenv_value(dotenv, "MISSING") is None
    assert "REDIS_URL" not in os.environ


def test_a_list_detail_becomes_the_message() -> None:
    response = api_exception_handler(exceptions.NotFound(["gone", "really"]), {})
    assert response.data["error"] == {"code": "not_found", "message": "gone really"}


@pytest.mark.parametrize("raw", ["", "  "])
def test_a_blank_json_setting_means_the_defaults(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("CF_TEST_MAPPING", raw)
    assert env_mapping("CF_TEST_MAPPING", {"a": 1}) == {"a": 1}


def test_sql_is_never_logged() -> None:
    logging_config: dict[str, Any] = settings.LOGGING
    assert logging_config["loggers"]["django.db.backends"]["level"] == "INFO"


def test_env_json_names_the_setting_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CF_TEST_JSON", "[1, 2")
    with pytest.raises(ImproperlyConfigured, match="CF_TEST_JSON is not valid JSON"):
        env_json("CF_TEST_JSON", None)


def test_unacknowledged_messages_outlive_the_longest_retry_countdown() -> None:
    options = settings.CELERY_BROKER_TRANSPORT_OPTIONS
    assert options["visibility_timeout"] > settings.GITHUB_MAX_RETRY_DELAY
    assert options["socket_timeout"] >= 2.0
