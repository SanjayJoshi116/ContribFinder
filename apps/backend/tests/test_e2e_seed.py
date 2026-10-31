"""Browser-test seeding (frontend-correctness D9): only the e2e settings can sign in without
GitHub, and the seed builds real pipeline output."""

import importlib
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.utils import timezone

from accounts.models import AuditEvent, User
from developers.models import DeveloperProfile
from e2e.builders import add_candidate, fresh_repo
from e2e.management.commands import e2e_seed
from issues.models import RecommendedIssue
from jobs.models import SyncJob
from recommendations.models import Recommendation
from repositories.models import Repository, RepositoryCandidate, RepositorySnapshot
from services import jobs
from services.repositories.staleness import RELEASED_MARK


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
    assert e2e.DATABASES["default"]["NAME"] == e2e_seed.E2E_DATABASE
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


@pytest.mark.parametrize(
    ("apps", "database", "message"),
    [
        (["accounts"], "contribfinder_e2e", "config.settings.e2e"),
        (["accounts", "e2e"], "contribfinder", "contribfinder_e2e database"),
    ],
    ids=["app-missing", "other-database"],
)
def test_the_seed_refuses_anything_but_the_e2e_database(
    apps: list[str], database: str, message: str
) -> None:
    with pytest.raises(CommandError, match=message):
        e2e_seed.refuse_unless_e2e(apps, database)


def test_the_seed_runs_on_the_e2e_database() -> None:
    e2e_seed.refuse_unless_e2e(["accounts", "e2e"], e2e_seed.E2E_DATABASE)


@pytest.mark.django_db
def test_seeding_again_replaces_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    # Users and sessions only: the pipeline is covered above.
    monkeypatch.setattr(e2e_seed, "_synced_user", e2e_seed._user)
    first = e2e_seed.seed(attempts=2)
    AuditEvent.objects.create(action="github_data_deleted", outcome="success")

    second = e2e_seed.seed(attempts=2)

    read = [*e2e_seed.READ_USERS, e2e_seed.UNSYNCED_USER]
    assert set(second) == {*read, *e2e_seed.MUTATING_USERS}
    assert all(isinstance(second[name], str) for name in read)  # shared by every attempt
    assert all(len(second[name]) == 2 for name in e2e_seed.MUTATING_USERS)  # one per attempt

    def keys(sessions: dict[str, str | list[str]]) -> list[str]:
        return [k for v in sessions.values() for k in ([v] if isinstance(v, str) else v)]

    old = keys(first)
    assert not Session.objects.filter(session_key__in=old).exists()
    assert not AuditEvent.objects.exists()
    signed_in = set()
    for key in keys(second):  # every attempt signs in as its own user
        client = Client()
        client.cookies[settings.SESSION_COOKIE_NAME] = key
        signed_in.add(client.get("/api/v1/auth/me").json()["github_username"])
    retries = {f"{n}{s}" for n in e2e_seed.MUTATING_USERS for s in ("", "-retry1")}
    assert signed_in == {*read, *retries}
    assert not Repository.objects.filter(full_name__contains=RELEASED_MARK).exists()
    assert User.objects.count() == len(signed_in)
    for snapshot in RepositorySnapshot.objects.select_related("repository"):
        pushed = snapshot.repository.pushed_at
        assert pushed is not None
        assert snapshot.days_since_push == (timezone.now() - pushed).days


@pytest.mark.django_db
def test_a_job_that_cannot_be_finished_fails_the_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    user = e2e_seed._user(0, "e2e-dashboard")
    monkeypatch.setattr(jobs, "finish_job", lambda *args, **kwargs: False)
    with pytest.raises(CommandError, match="Could not finish"):
        e2e_seed._record(user, jobs.SYNC)
    assert SyncJob.objects.get(user=user).status == SyncJob.Status.RUNNING


@pytest.mark.django_db
def test_seeded_jobs_end_completed_with_every_step_done() -> None:
    user = e2e_seed._user(0, "e2e-dashboard")
    e2e_seed._record(user, jobs.SYNC)
    job = SyncJob.objects.get(user=user)
    assert job.status == SyncJob.Status.COMPLETED
    assert set(job.steps.values()) == {SyncJob.StepState.DONE}


@pytest.mark.django_db
def test_add_candidate_keeps_the_candidate_as_recent_as_its_records() -> None:
    now = timezone.now()
    profile = DeveloperProfile.objects.create(user=e2e_seed._user(0, "dev"), analyzed_at=now)
    repo = fresh_repo()

    cand = add_candidate(profile, repo, seen=now - timedelta(days=2), discovery_seen=now)
    assert cand.last_seen_at == now  # never older than its own record

    later = now + timedelta(hours=1)
    add_candidate(profile, repo, source="topic_search", seen=later)
    assert RepositoryCandidate.objects.get(pk=cand.pk).last_seen_at == later
