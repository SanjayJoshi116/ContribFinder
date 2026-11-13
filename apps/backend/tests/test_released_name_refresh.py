"""A repository that gives up its name is refreshed right away (released-name-refresh)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
import pytest
from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from e2e.builders import add_candidate, fresh_repo
from repositories import tasks
from services.repositories import backlog
from services.repositories.analysis import Outcome, RepositoryAnalysisService

from .repo_fixtures import API, expire_parts, same_repository, take_name
from .shared_fixtures import developer, public_client, single_band  # noqa: F401


@pytest.fixture(autouse=True)
def worker(settings: Any) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = False  # a worker runs the tasks


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    queued: list[int] = []
    monkeypatch.setattr(tasks.sync_repository, "delay", queued.append)
    return queued


def test_released_name_refreshed_after_commit(
    developer, sent, django_capture_on_commit_callbacks
) -> None:
    old = fresh_repo(1, "org/tool")
    add_candidate(developer, old)

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        take_name()
        assert sent == []  # nothing is sent before the commit
        old.refresh_from_db()
        assert old.refresh_queued_at is not None
    for callback in callbacks:
        callback()

    assert sent == [old.pk]
    # The periodic path does not queue it a second time.
    now = timezone.now()
    backlog.mark_stale(now)
    assert old.pk not in [pk for pk, _ in backlog.queue_batch(now)]


def test_rolled_back_release_queues_nothing(
    developer, sent, django_capture_on_commit_callbacks
) -> None:
    old = fresh_repo(1, "org/tool")
    add_candidate(developer, old)

    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(RuntimeError),
        transaction.atomic(),
    ):
        take_name()
        raise RuntimeError

    old.refresh_from_db()
    assert (old.full_name, old.refresh_queued_at) == ("org/tool", None)
    assert sent == []


def test_recent_refresh_failure_does_not_hold_it_back(
    developer, sent, django_capture_on_commit_callbacks
) -> None:
    old = fresh_repo(1, "org/tool", refresh_failed_at=timezone.now())
    add_candidate(developer, old)

    with django_capture_on_commit_callbacks(execute=True):
        take_name()

    assert sent == [old.pk]


@pytest.mark.parametrize(
    "fields",
    [
        {"lifecycle": "refreshing", "claimed_at": timezone.now()},  # another analysis holds it
        {"lifecycle": "failed"},  # its retry fetches everything
        {"refresh_queued_at": timezone.now() - timedelta(minutes=5)},  # already queued
    ],
    ids=["in-progress", "failed", "queued"],
)
def test_holder_left_to_its_own_path(
    developer, sent, django_capture_on_commit_callbacks, fields
) -> None:
    old = fresh_repo(1, "org/tool", **fields)
    add_candidate(developer, old)
    stamp = old.refresh_queued_at

    with django_capture_on_commit_callbacks(execute=True):
        take_name()

    old.refresh_from_db()
    assert old.full_name == "org/tool~1"
    assert old.refresh_queued_at == stamp
    assert sent == []


def test_holder_in_no_pool_not_queued(db, sent, django_capture_on_commit_callbacks) -> None:
    old = fresh_repo(1, "org/tool")

    with django_capture_on_commit_callbacks(execute=True):
        take_name()

    old.refresh_from_db()
    assert (old.full_name, old.refresh_queued_at) == ("org/tool~1", None)
    assert sent == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"CELERY_TASK_ALWAYS_EAGER": True},  # no worker: never analyzed inline
        {"GITHUB_CLIENT_ID": ""},  # no app credentials
    ],
    ids=["inline-tasks", "no-credentials"],
)
def test_nothing_queued_without_a_worker_or_credentials(
    developer, sent, django_capture_on_commit_callbacks, overrides
) -> None:
    old = fresh_repo(1, "org/tool")
    add_candidate(developer, old)

    with override_settings(**overrides), django_capture_on_commit_callbacks(execute=True):
        take_name()

    old.refresh_from_db()
    assert (old.full_name, old.refresh_queued_at) == ("org/tool~1", None)
    assert sent == []


def test_rejected_credentials_hold_it_back(
    developer, sent, django_capture_on_commit_callbacks
) -> None:
    old = fresh_repo(
        1, "org/tool", refresh_failed_at=timezone.now(), lifecycle_error=backlog.AUTH_INVALID
    )
    add_candidate(developer, old)

    with django_capture_on_commit_callbacks(execute=True):
        take_name()

    old.refresh_from_db()
    assert (old.full_name, old.refresh_queued_at) == ("org/tool~1", None)
    assert sent == []


def test_name_released_during_its_analysis_queued_again(
    client, respx_mock, developer, sent, django_capture_on_commit_callbacks
) -> None:
    old = fresh_repo(1, "org/tool", refresh_queued_at=timezone.now())  # this run's own stamp
    add_candidate(developer, old)
    expire_parts(old, ["readme"])

    def renamed_meanwhile(request: httpx.Request) -> httpx.Response:
        take_name()  # skipped: another analysis holds it
        return httpx.Response(200, text="# Someone else's README")

    same_repository(respx_mock, "org/tool", 1)
    respx_mock.get(f"{API}/repos/org/tool/readme").mock(side_effect=renamed_meanwhile)

    with django_capture_on_commit_callbacks(execute=True):
        outcome = RepositoryAnalysisService(client).run(old.pk, ["readme"])

    assert outcome == Outcome.SKIPPED
    old.refresh_from_db()
    assert (old.full_name, old.lifecycle) == ("org/tool~1", "indexed")
    assert old.refresh_queued_at is not None
    assert sent == [old.pk]
