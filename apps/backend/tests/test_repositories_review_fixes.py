"""Review sweep of ``repositories/`` (Bug_Backlog.md batch 38, REPO-1…REPO-8)."""

import logging
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from developers.models import DeveloperProfile
from e2e.builders import add_candidate, make_candidate_repo
from repositories import tasks
from repositories.models import (
    Repository,
    RepositoryCandidate,
    RepositorySnapshot,
    UserRepository,
)
from services.repositories.analysis import RepositoryAnalysisService

from .repo_fixtures import API
from .shared_fixtures import assert_view_only, changelist_queries

pytestmark = pytest.mark.django_db

ADMINS = [Repository, UserRepository, RepositorySnapshot, RepositoryCandidate]


@pytest.fixture
def profile(user) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


# --- View-only admin (REPO-5, REPO-6, REPO-7) ---------------------------------------------


@pytest.mark.parametrize("model", ADMINS, ids=lambda m: m.__name__)
def test_staff_cannot_add_change_or_delete_repository_data(admin_user: User, model) -> None:
    assert_view_only(model, admin_user)


def test_repository_page_cannot_change_lifecycle(admin_client: Client) -> None:
    repo = make_candidate_repo(1, lifecycle="indexed", is_eligible=False)
    url = f"/admin/repositories/repository/{repo.pk}/change/"
    assert admin_client.get(url).status_code == 200
    response = admin_client.post(url, {"lifecycle": "recommendable", "is_eligible": "on"})
    assert response.status_code == 403
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.is_eligible) == ("indexed", False)


@pytest.mark.parametrize("path", ["userrepository", "repositorysnapshot", "repositorycandidate"])
def test_changelist_query_count_does_not_grow_with_rows(admin_client: Client, path: str) -> None:
    url = f"/admin/repositories/{path}/"
    now = timezone.now()

    def build(n: int) -> None:
        owner = User.objects.create(username=f"u{n}")
        repo = make_candidate_repo(100 + n)
        UserRepository.objects.create(user=owner, repository=repo, relation="owner")
        RepositorySnapshot.objects.create(
            repository=repo,
            captured_at=now,
            stars=1,
            forks=0,
            open_issues=0,
            activity_label="recently_active",
            thresholds_version="x",
        )
        developer = DeveloperProfile.objects.create(user=owner, analyzed_at=now)
        add_candidate(developer, repo)

    build(0)
    one = changelist_queries(admin_client, url)
    for n in range(1, 4):
        build(n)
    assert changelist_queries(admin_client, url) == one


# --- Refresh decision (REPO-1, REPO-2, REPO-4) ---------------------------------------------


def test_inline_refresh_never_retries_inline(respx_mock, monkeypatch) -> None:
    repo = make_candidate_repo(
        7, "encode/httpx", lifecycle="stale", is_eligible=True, previous_lifecycle="recommendable"
    )
    route = respx_mock.get(f"{API}/repos/encode/httpx").respond(429, headers={"Retry-After": "30"})

    def no_retry(**_kwargs):
        raise AssertionError("an inline run must not retry")

    monkeypatch.setattr(tasks.sync_repository, "retry", no_retry)
    tasks.sync_repository.delay(repo.pk)  # eager in tests
    assert route.call_count == 1
    repo.refresh_from_db()
    assert (repo.lifecycle, repo.lifecycle_error) == ("stale", "github_rate_limited")


def test_unexpected_error_is_logged_with_its_traceback(monkeypatch, caplog) -> None:
    repo = make_candidate_repo(7, "encode/httpx", lifecycle="stale", is_eligible=True)

    def broken(self, repo_id, parts):
        raise TypeError("bug in analysis")

    monkeypatch.setattr(RepositoryAnalysisService, "run", broken)
    with caplog.at_level(logging.WARNING, logger="repositories.tasks"):
        tasks.sync_repository.delay(repo.pk)
    (record,) = [r for r in caplog.records if "refresh failed" in r.getMessage()]
    assert record.exc_info is not None and record.exc_info[0] is TypeError
    repo.refresh_from_db()
    assert repo.lifecycle_error == "internal_error"


def test_a_scheduled_retry_renews_the_queued_time(respx_mock, monkeypatch) -> None:
    long_ago = timezone.now() - timedelta(hours=2)
    repo = make_candidate_repo(
        7, "encode/httpx", lifecycle="stale", is_eligible=True, previous_lifecycle="recommendable"
    )
    Repository.objects.filter(pk=repo.pk).update(refresh_queued_at=long_ago)
    respx_mock.get(f"{API}/repos/encode/httpx").respond(429, headers={"Retry-After": "30"})

    class Retried(Exception):
        pass

    monkeypatch.setattr(tasks.sync_repository, "retry", lambda **_: Retried())
    with pytest.raises(Retried):
        tasks.sync_repository(repo.pk)  # called directly: a worker run, not eager
    repo.refresh_from_db()
    assert repo.refresh_queued_at is not None
    assert repo.refresh_queued_at > timezone.now() - timedelta(minutes=1)


# --- Refused sends (REPO-3) ----------------------------------------------------------------


def test_a_refused_send_is_not_left_queued(profile, monkeypatch) -> None:
    now = timezone.now()
    repos = [
        make_candidate_repo(
            n,
            lifecycle="stale",
            stale_parts=["metadata"],
            lifecycle_changed_at=now - timedelta(hours=n),
        )
        for n in (3, 2, 1)  # oldest first: queued in this order
    ]
    for repo in repos:
        add_candidate(profile, repo)
    sent: list[int] = []

    def delay(pk: int) -> None:
        if pk == repos[1].pk:
            raise ConnectionError("broker down")
        sent.append(pk)

    monkeypatch.setattr(tasks.sync_repository, "delay", delay)
    assert tasks.process_repository_backlog() == 2
    assert sent == [repos[0].pk, repos[2].pk]
    stamps = dict(Repository.objects.values_list("pk", "refresh_queued_at"))
    assert stamps[repos[0].pk] is not None and stamps[repos[2].pk] is not None
    assert stamps[repos[1].pk] is None

    sent.clear()
    monkeypatch.setattr(tasks.sync_repository, "delay", sent.append)
    assert tasks.process_repository_backlog() == 1
    assert sent == [repos[1].pk]
