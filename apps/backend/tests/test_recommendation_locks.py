"""recommendation-consistency D2: generation, feedback and issue refreshes share one lock order.

Each test pauses a generation in the middle of its write (after it locked the developer's
recommendations and the matched issues), starts the competing write, waits until that write
is blocked on a lock, then lets the generation finish. With opposite lock orders PostgreSQL
reports a deadlock in one of them.
"""

import threading
import time
from collections.abc import Callable
from typing import Any, cast

import pytest
from django.db import connection, transaction
from django.utils import timezone

from feedback.models import DismissedRepository, RecommendationFeedback
from recommendations.models import Recommendation, ScoringConfig
from services import feedback
from services.github.client import GitHubClient
from services.matching.issues import snapshot as issue_snapshot
from services.ranking.config import V2_PARAMS, V2_WEIGHTS
from services.repositories.analysis import RepositoryAnalysisService

from .test_issue_matching import django_issues
from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    generate,
    pool,
)

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.respx(assert_all_called=False)]


@pytest.fixture(autouse=True)
def _active_config() -> None:
    # Transactional tests start from an empty database: the seeded configurations are gone.
    ScoringConfig.objects.get_or_create(
        version="v2-deterministic",
        defaults={"weights": V2_WEIGHTS, "params": V2_PARAMS, "is_active": True},
    )


def _thread(target: Callable[[], Any], errors: list[BaseException]) -> threading.Thread:
    def run() -> None:
        try:
            target()
        except BaseException as exc:  # reported by the test
            errors.append(exc)
        finally:
            connection.close()

    thread = threading.Thread(target=run)
    thread.start()
    return thread


def _wait_for_lock_waiter(timeout: float = 10.0) -> None:
    """Return once another connection is waiting for a lock (the competing write)."""
    deadline = time.monotonic() + timeout
    with connection.cursor() as cursor:
        while time.monotonic() < deadline:
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE wait_event_type = 'Lock' AND datname = current_database()"
            )
            if cursor.fetchone()[0]:
                return
            time.sleep(0.05)
    raise AssertionError("the competing write never waited for a lock")


def _paused_generation(monkeypatch, user) -> tuple[threading.Event, threading.Event]:
    """Run a generation in a thread that stops after locking recommendations and issues."""
    paused, resume = threading.Event(), threading.Event()

    def snapshot(issues):
        if not paused.is_set():
            paused.set()
            assert resume.wait(20)
        return issue_snapshot(issues)

    monkeypatch.setattr("services.ranking.service.issue_snapshot", snapshot)
    return paused, resume


def test_dismiss_during_a_generation_write(user, developer, pool, monkeypatch) -> None:  # noqa: F811
    generate(user)
    rec = Recommendation.objects.get(repository=pool["django"])
    paused, resume = _paused_generation(monkeypatch, user)
    errors: list[BaseException] = []

    generation = _thread(lambda: generate(user), errors)
    assert paused.wait(20)
    dismiss = _thread(lambda: feedback.dismiss(user, rec), errors)
    _wait_for_lock_waiter()  # the dismiss waits for the generation's profile lock
    resume.set()
    generation.join(30)
    dismiss.join(30)

    assert errors == []
    assert DismissedRepository.objects.filter(user=user, repository=pool["django"]).exists()
    assert not Recommendation.objects.filter(repository=pool["django"]).exists()


def test_issue_refresh_during_a_generation_write(user, developer, pool, monkeypatch) -> None:  # noqa: F811
    django_issues(pool["django"])
    generate(user)
    assert Recommendation.objects.get(repository=pool["django"]).relevant_issue_count == 3
    paused, resume = _paused_generation(monkeypatch, user)
    errors: list[BaseException] = []

    def close_all_issues() -> None:
        service = RepositoryAnalysisService(cast(GitHubClient, None))
        with transaction.atomic():
            service._store_issues(pool["django"], [], timezone.now())

    generation = _thread(lambda: generate(user), errors)
    assert paused.wait(20)
    refresh = _thread(close_all_issues, errors)
    _wait_for_lock_waiter()  # the refresh waits for the issues the generation locked
    resume.set()
    generation.join(30)
    refresh.join(30)

    assert errors == []
    assert not pool["django"].issues.exists()


def test_simultaneous_views_are_recorded_once(user, developer, pool) -> None:  # noqa: F811
    generate(user)
    rec = Recommendation.objects.get(repository=pool["django"])
    barrier = threading.Barrier(2, timeout=10)
    errors: list[BaseException] = []

    def view() -> None:
        barrier.wait()
        feedback.record(user, rec, "viewed")

    threads = [_thread(view, errors) for _ in range(2)]
    for thread in threads:
        thread.join(30)
    assert errors == []
    assert RecommendationFeedback.objects.filter(user=user, action="viewed").count() == 1


def test_issue_update_during_a_generation_write(user, developer, pool, monkeypatch) -> None:  # noqa: F811
    from services.github.client import IssueData

    issues = django_issues(pool["django"])
    generate(user)
    paused, resume = _paused_generation(monkeypatch, user)
    errors: list[BaseException] = []

    def refresh_open_issues() -> None:
        fetched = [
            IssueData(
                github_id=issue.github_id,
                number=issue.number,
                title=f"{issue.title} (edited)",
                body=issue.body,
                labels=tuple(issue.raw_labels),
                state="open",
                is_locked=False,
                has_assignee=False,
                comments=issue.comments,
                html_url=issue.html_url,
                created_at=issue.github_created_at,
                updated_at=timezone.now(),
            )
            for issue in reversed(issues)  # updated out of pk order
        ]
        service = RepositoryAnalysisService(cast(GitHubClient, None))
        with transaction.atomic():
            service._store_issues(pool["django"], fetched, timezone.now())

    generation = _thread(lambda: generate(user), errors)
    assert paused.wait(20)
    refresh = _thread(refresh_open_issues, errors)
    _wait_for_lock_waiter()  # the refresh waits for the issues the generation locked
    resume.set()
    generation.join(30)
    refresh.join(30)

    assert errors == []
    assert pool["django"].issues.filter(title__endswith="(edited)").count() == 3


def test_dismiss_after_a_generation_dropped_the_recommendation(user, developer, pool) -> None:  # noqa: F811
    generate(user)
    stale = Recommendation.objects.get(repository=pool["django"])  # the page's copy
    Recommendation.objects.filter(pk=stale.pk).delete()  # a generation dropped it, committed

    feedback.dismiss(user, stale)  # commits here: no reference to the deleted row

    assert DismissedRepository.objects.filter(user=user, repository=pool["django"]).exists()
    event = RecommendationFeedback.objects.get(user=user, action="dismissed")
    assert event.recommendation is None and event.repository_full_name == "encode/django-tool"


def test_view_of_a_dropped_recommendation_records_nothing(user, developer, pool) -> None:  # noqa: F811
    generate(user)
    stale = Recommendation.objects.get(repository=pool["django"])
    Recommendation.objects.filter(pk=stale.pk).delete()
    assert feedback.record(user, stale, "viewed") is False
    assert not RecommendationFeedback.objects.filter(user=user).exists()
