"""Browser-test seeding (frontend-correctness D9): only the e2e settings can sign in without
GitHub, and the seed builds real pipeline output."""

import importlib
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from e2e.management.commands import e2e_seed
from issues.models import RecommendedIssue
from recommendations.models import Recommendation


def test_seed_command_is_unknown_outside_e2e_settings(tmp_path: Path) -> None:
    assert "e2e" not in settings.INSTALLED_APPS
    with pytest.raises(CommandError, match="Unknown command"):
        call_command("e2e_seed", out=str(tmp_path / "sessions.json"))


def test_only_the_e2e_settings_install_the_app(monkeypatch: pytest.MonkeyPatch) -> None:
    development = importlib.import_module("config.settings.development")
    monkeypatch.setenv("REDIS_URL", "redis://prod-redis:6379/0")
    production = importlib.reload(importlib.import_module("config.settings.production"))
    e2e = importlib.import_module("config.settings.e2e")

    assert "e2e" not in development.INSTALLED_APPS
    assert "e2e" not in production.INSTALLED_APPS
    assert "e2e" in e2e.INSTALLED_APPS
    assert e2e.CELERY_TASK_ALWAYS_EAGER is True
    assert e2e.GITHUB_API_BASE_URL.startswith("http://127.0.0.1:")
    assert e2e.DATABASES["default"]["NAME"] == "contribfinder_e2e"
    # Importing it changed nothing in the running settings.
    assert settings.DATABASES["default"]["NAME"] != "contribfinder_e2e"


@pytest.mark.django_db
def test_seed_builds_recommendations_and_sessions() -> None:
    e2e_seed._seed_pool()
    user = e2e_seed._synced_user(0, "e2e-dashboard")
    unsynced = e2e_seed._user(1, "e2e-unsynced")

    recommendations = Recommendation.objects.filter(developer__user=user)
    assert recommendations.count() > 20
    assert RecommendedIssue.objects.filter(recommendation__developer__user=user).exists()
    assert not Recommendation.objects.filter(developer__user=unsynced).exists()

    client = Client()
    client.cookies[settings.SESSION_COOKIE_NAME] = e2e_seed._session(user)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["github_username"] == "e2e-dashboard"
