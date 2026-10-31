"""Seed the browser-test database: users, their GitHub-derived data and a signed-in session
each (end-to-end settings only)."""

from argparse import ArgumentParser, ArgumentTypeError
from collections.abc import Callable
from datetime import timedelta
from itertools import count
from typing import Any

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test import Client
from django.utils import timezone

from accounts.models import AuditEvent, User
from core.reports import write_json
from developers.models import DeveloperProfile, Interest, Skill
from e2e.builders import add_candidate, fresh_repo, make_issue
from github.models import GitHubAccount, GitHubProfile
from jobs.models import SyncJob
from repositories.models import (
    Repository,
    RepositoryDependency,
    RepositoryLanguage,
    RepositorySnapshot,
    RepositoryTopic,
    UserRepository,
)
from services import jobs
from services.crypto import encrypt_token
from services.profiling.analysis import ProfileAnalysisService
from services.ranking.service import RecommendationService

# The only database the seed may replace (config.settings.e2e pins it).
E2E_DATABASE = "contribfinder_e2e"
# Read by several tests, changed by none: one session serves every attempt.
READ_USERS = ("e2e-dashboard",)
# One user per test that changes data, seeded once per attempt (``--attempts``: Playwright's
# retries + 1), so a retry starts from seeded data. The sessions file maps these to a list (one
# session per attempt) and the rest to one session; e2e/fixtures.ts ``signInAs`` reads only it.
MUTATING_USERS = ("e2e-save", "e2e-dismiss", "e2e-delete")
UNSYNCED_USER = "e2e-unsynced"
PUSHED_DAYS_AGO = 2  # every seeded candidate, and its snapshot
CANDIDATES = 25  # more than one page (20), so pagination and filters show
WITH_ISSUES = 3  # the best candidates carry relevant issues
Step = SyncJob.StepState


class Command(BaseCommand):
    help = (
        "Create the end-to-end database if needed, migrate it, replace its data with the "
        "browser-test users and write their session ids as JSON."
    )
    requires_system_checks: list[str] = []

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--out", metavar="PATH", required=True, help="Session ids file.")
        parser.add_argument(
            "--attempts",
            type=_positive,
            default=1,
            help="Attempts per browser test (retries + 1): one user per attempt for tests that "
            "change data.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        refuse_unless_e2e(settings.INSTALLED_APPS, settings.DATABASES["default"]["NAME"])
        _create_database()
        call_command("migrate", interactive=False, verbosity=0)
        sessions = seed(options["attempts"])
        out = options["out"]
        write_json(out, sessions, what="Sessions")
        self.stdout.write(f"Seeded the browser-test users; sessions in {out}")


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise ArgumentTypeError("must be at least 1")
    return number


def refuse_unless_e2e(installed_apps: list[str], database: str) -> None:
    """The seed deletes every user and repository: only the end-to-end settings, and only their
    database, may run it."""
    if "e2e" not in installed_apps:
        raise CommandError("Only for config.settings.e2e.")
    if database != E2E_DATABASE:
        raise CommandError(f"Only for the {E2E_DATABASE} database, not {database}.")


def seed(attempts: int = 1) -> dict[str, str | list[str]]:
    """Replace the data with the browser-test users; returns their session ids by name: a list
    with one per attempt for users that tests change (attempt n > 0 signs in as
    ``<name>-retry<n>``), one id for the rest, shared by every attempt."""
    _reset()
    _seed_pool()
    index = count()

    def synced(name: str) -> str:
        return _session(_synced_user(next(index), name))

    sessions: dict[str, str | list[str]] = {name: synced(name) for name in READ_USERS}
    for name in MUTATING_USERS:
        # Not "~": it marks a released repository name (staleness.RELEASED_MARK).
        sessions[name] = [synced(f"{name}-retry{n}" if n else name) for n in range(attempts)]
    sessions[UNSYNCED_USER] = _session(_user(next(index), UNSYNCED_USER))
    return sessions


def _create_database() -> None:
    name = settings.DATABASES["default"]["NAME"]
    with connection._nodb_cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [name])
        if cursor.fetchone() is None:
            cursor.execute(f"CREATE DATABASE {connection.ops.quote_name(name)}")


def _reset() -> None:
    """Everything but migration-seeded rows (scoring configurations): users cascade to their
    accounts, jobs, profiles and feedback; repositories and the catalog are shared. Sessions and
    audit entries have no cascade from users."""
    Session.objects.all().delete()
    AuditEvent.objects.all().delete()
    User.objects.all().delete()
    Repository.objects.all().delete()
    Skill.objects.all().delete()
    Interest.objects.all().delete()


def _seed_pool() -> None:
    for n in range(1, CANDIDATES + 1):
        repo = fresh_repo(
            50_000 + n,
            f"seed-org/project-{n:02d}",
            description=f"Seeded Python project {n} for browser tests.",
            stars=2000 - n * 50,
            has_contributing=True,
            has_good_first_issue_label=n <= WITH_ISSUES,
            pushed_at=timezone.now() - timedelta(days=PUSHED_DAYS_AGO),
        )
        RepositoryLanguage.objects.create(repository=repo, language="Python", bytes=9000)
        RepositoryTopic.objects.create(repository=repo, topic="developer-tools")
        if n % 2:
            RepositoryDependency.objects.create(
                repository=repo, ecosystem="pypi", name="django", manifest_path="pyproject.toml"
            )
        RepositorySnapshot.objects.create(
            repository=repo,
            captured_at=timezone.now(),
            stars=repo.stars,
            forks=10,
            open_issues=5,
            activity_label="recently_active",
            thresholds_version="e2e",
            days_since_push=PUSHED_DAYS_AGO,
            commits_90d=60,
            prs_merged_90d=20,
            contributors=30,
        )
        if n <= WITH_ISSUES:
            for number in (1, 2):
                make_issue(
                    repo,
                    number,
                    title=f"Fix the Django settings loader ({number})",
                    body="The loader ignores an empty value. Python and Django only.",
                    raw_labels=["good first issue", "bug"],
                    labels=["good_first_issue", "bug"],
                    contribution_type="bug_fix",
                    difficulty="beginner",
                    technologies=[
                        {"slug": "python", "source": "body"},
                        {"slug": "django", "source": "body"},
                    ],
                )


def _user(index: int, name: str) -> User:
    user = User(username=name, display_name=name)
    user.set_unusable_password()
    user.save()
    GitHubAccount.objects.create(
        user=user,
        github_id=900_000 + index,
        username=name,
        access_token_encrypted=encrypt_token(f"gho_e2e_{index:032d}"),
    )
    return user


def _synced_user(index: int, name: str) -> User:
    """A user whose sync, analysis, discovery and generation all completed."""
    user = _user(index, name)
    now = timezone.now()
    GitHubProfile.objects.create(
        user=user,
        github_id=900_000 + index,
        login=name,
        name=f"E2E {name}",
        has_profile_readme=True,
        profile_readme="## Tech Stack\nPython, Django\n\nI build developer tools.",
        github_created_at=now - timedelta(days=5 * 365),
        synced_at=now,
    )
    for n, (language, topics) in enumerate(
        (("Python", ("developer-tools", "cli")), ("Python", ("django",)), ("TypeScript", ()))
    ):
        repo = Repository.objects.create(
            github_id=800_000 + index * 10 + n,
            owner_login=name,
            name=f"own-{n}",
            full_name=f"{name}/own-{n}",
            html_url=f"https://github.com/{name}/own-{n}",
            primary_language=language,
            pushed_at=now - timedelta(days=n + 1),
            synced_at=now,
        )
        RepositoryLanguage.objects.create(repository=repo, language=language, bytes=5000)
        for topic in topics:
            RepositoryTopic.objects.create(repository=repo, topic=topic)
        if language == "Python":
            RepositoryDependency.objects.create(
                repository=repo, ecosystem="pypi", name="django", manifest_path="pyproject.toml"
            )
        UserRepository.objects.create(user=user, repository=repo, relation="owner")

    _record(user, jobs.SYNC)
    _run(user, jobs.ANALYSIS, lambda job: ProfileAnalysisService(user, job=job).run())
    profile = DeveloperProfile.objects.get(user=user)
    for rank, repo in enumerate(
        Repository.objects.filter(full_name__startswith="seed-org/").order_by("github_id"),
        start=1,
    ):
        add_candidate(profile, repo, rank=rank)
    _record(user, jobs.DISCOVERY)
    _run(user, jobs.RECOMMENDATIONS, lambda job: RecommendationService(job).run())
    return user


def _run(user: User, job_type: str, runner: Callable[[SyncJob], object]) -> None:
    """Run a job's service the way a worker does (claim, run, finish), without its follow-up
    jobs: a discovery would call GitHub."""
    job = jobs.claim_job(jobs.new_job(user, job_type).pk)
    if job is None:  # pragma: no cover - a fresh PENDING job is always claimable
        raise CommandError(f"Could not claim the {job_type} job")
    runner(job)
    done = dict.fromkeys(job.steps, Step.DONE)
    if not jobs.finish_job(job, SyncJob.Status.COMPLETED, steps=done):
        raise CommandError(f"Could not finish the {job_type} job")


def _record(user: User, job_type: str) -> None:
    """A completed job whose data the seed wrote directly (sync, discovery)."""
    _run(user, job_type, lambda job: None)


def _session(user: User) -> str:
    client = Client()
    client.force_login(user)
    return client.session.session_key  # type: ignore[return-value]  # set by force_login
