"""Feedback events, save and dismiss: models, service and API (Phase 8a, groups 1-3)."""

from datetime import timedelta
from typing import cast

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from developers.models import DeveloperProfile
from feedback.models import DismissedRepository, RecommendationFeedback, SavedRepository
from github.models import GitHubAccount
from jobs.models import SyncJob
from recommendations.models import Recommendation
from repositories.models import Repository
from services import feedback
from services.ranking.service import RecommendationService

from .factories import GitHubAccountFactory
from .repo_fixtures import add_candidate
from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    generate,
    pool,
    ready_repo,
    running_job,
)

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]

RECS = "/api/v1/recommendations"


@pytest.fixture
def recs(user, developer, pool):  # noqa: F811
    generate(user)
    return {
        name: Recommendation.objects.filter(repository=repo).first() for name, repo in pool.items()
    }


def events(user, action: str | None = None):
    qs = RecommendationFeedback.objects.filter(user=user)
    return qs.filter(action=action) if action else qs


def other_user() -> User:
    return cast(GitHubAccount, GitHubAccountFactory()).user


# --- Models ---------------------------------------------------------------------------


def test_save_and_dismissal_are_unique_per_user(user, recs) -> None:
    repo = recs["django"].repository
    SavedRepository.objects.create(user=user, repository=repo)
    DismissedRepository.objects.create(user=user, repository=repo)
    for model in (SavedRepository, DismissedRepository):
        with pytest.raises(IntegrityError), transaction.atomic():
            model.objects.create(user=user, repository=repo)


def test_feedback_survives_recommendation_and_repository_deletion(user, recs) -> None:
    rec = recs["django"]
    feedback.record(user, rec, "viewed")
    rec.delete()
    event = events(user).get()
    assert event.recommendation is None
    assert (event.repository_full_name, event.match_label, event.rank) == (
        "encode/django-tool",
        "strong",
        1,
    )
    Repository.objects.filter(pk=event.repository_id).delete()
    event.refresh_from_db()
    assert event.repository is None
    assert event.config_version == "v2-deterministic"


def test_saves_dismissals_and_feedback_cascade_with_the_user(user, recs) -> None:
    feedback.save(user, recs["django"])
    feedback.dismiss(user, recs["plain"])
    user.delete()
    assert not SavedRepository.objects.exists()
    assert not DismissedRepository.objects.exists()
    assert not RecommendationFeedback.objects.exists()


# --- Service --------------------------------------------------------------------------


def test_view_recorded_once_within_the_window(user, recs, settings) -> None:
    rec = recs["django"]
    assert feedback.record(user, rec, "viewed") is True
    assert feedback.record(user, rec, "viewed") is False
    assert events(user, "viewed").count() == 1
    events(user).update(
        created_at=timezone.now() - timedelta(minutes=settings.FEEDBACK_VIEW_DEDUP_MINUTES + 1)
    )
    assert feedback.record(user, rec, "viewed") is True
    assert events(user, "viewed").count() == 2


def test_other_actions_are_not_deduplicated(user, recs) -> None:
    feedback.record(user, recs["django"], "opened_repository")
    feedback.record(user, recs["django"], "opened_repository")
    assert events(user, "opened_repository").count() == 2


def test_save_is_idempotent_and_unsave_records_once(user, recs) -> None:
    rec = recs["django"]
    first = feedback.save(user, rec)
    again = feedback.save(user, rec)
    assert first.pk == again.pk and first.saved_at == again.saved_at
    assert events(user, "saved").count() == 1
    assert feedback.unsave(user, rec.repository_id) is True
    assert feedback.unsave(user, rec.repository_id) is False
    unsaved = events(user, "unsaved").get()
    assert (unsaved.recommendation_id, unsaved.match_label) == (rec.pk, "strong")


def test_dismiss_removes_recommendation_and_unsaves(user, recs) -> None:
    rec = recs["django"]
    feedback.save(user, rec)
    feedback.dismiss(user, rec)
    assert not Recommendation.objects.filter(pk=rec.pk).exists()
    assert not SavedRepository.objects.filter(user=user).exists()
    assert DismissedRepository.objects.filter(user=user, repository=rec.repository).exists()
    event = events(user, "dismissed").get()
    assert (event.recommendation, event.rank, event.repository_full_name) == (
        None,
        1,
        "encode/django-tool",
    )


def test_dismissed_repository_absent_after_regeneration(user, recs, pool) -> None:  # noqa: F811
    feedback.dismiss(user, recs["django"])
    generate(user)
    repos = list(Recommendation.objects.order_by("rank").values_list("repository_id", "rank"))
    assert pool["django"].pk not in [r for r, _ in repos]
    assert [rank for _, rank in repos] == list(range(1, len(repos) + 1))


def test_dismissal_during_a_run_is_honored(user, recs, pool, monkeypatch) -> None:  # noqa: F811
    from services.matching.features import load_candidates as real_load

    def load_then_dismiss(profile):
        candidates = real_load(profile)  # the run already loaded the repository
        DismissedRepository.objects.create(user=user, repository=pool["django"])
        return candidates

    monkeypatch.setattr("services.ranking.service.load_candidates", load_then_dismiss)
    Recommendation.objects.all().delete()
    job = running_job(user)
    RecommendationService(job).run()
    ranks = list(Recommendation.objects.order_by("rank").values_list("repository_id", "rank"))
    assert pool["django"].pk not in [r for r, _ in ranks]
    assert [rank for _, rank in ranks] == list(range(1, len(ranks) + 1))
    job.refresh_from_db()
    assert job.metadata["kept"] == len(ranks)


def test_restore_records_and_starts_a_generation(user, recs, pool, monkeypatch) -> None:  # noqa: F811
    queued: list[int] = []
    monkeypatch.setattr(
        "recommendations.tasks.generate_recommendations.delay", lambda pk: queued.append(pk)
    )
    feedback.dismiss(user, recs["django"])
    assert feedback.restore(user, pool["django"].pk) is True
    assert not DismissedRepository.objects.exists()
    assert events(user, "undismissed").count() == 1
    assert (
        SyncJob.objects.filter(user=user, job_type="recommendation_generation")
        .exclude(status="COMPLETED")
        .exists()
    )
    assert feedback.restore(user, pool["django"].pk) is False


def test_feedback_does_not_change_scores(user, recs) -> None:
    before = sorted(Recommendation.objects.values_list("repository_id", "score", "rank"))
    for _ in range(5):
        feedback.record(user, recs["plain"], "opened_repository")
    feedback.record(user, recs["plain"], "viewed")
    feedback.save(user, recs["plain"])
    generate(user)
    after = sorted(Recommendation.objects.values_list("repository_id", "score", "rank"))
    assert after == before


# --- API ------------------------------------------------------------------------------


def test_post_feedback(signed_in_client: APIClient, user, recs) -> None:
    rec = recs["django"]
    response = signed_in_client.post(
        f"{RECS}/{rec.pk}/feedback", {"action": "opened_repository"}, format="json"
    )
    assert response.status_code == 204
    assert events(user, "opened_repository").get().recommendation_id == rec.pk


@pytest.mark.parametrize("action", ["saved", "dismissed", "nope", ""])
def test_post_feedback_rejects_other_actions(signed_in_client: APIClient, user, recs, action):
    response = signed_in_client.post(
        f"{RECS}/{recs['django'].pk}/feedback", {"action": action}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert not events(user).exists()


@pytest.mark.parametrize(
    ("method", "suffix"),
    [("post", "feedback"), ("post", "save"), ("delete", "save"), ("post", "dismiss")],
)
def test_other_users_recommendation_is_404(
    api_client: APIClient, recs, method: str, suffix: str
) -> None:
    other = other_user()
    DeveloperProfile.objects.create(user=other, analyzed_at=timezone.now())
    api_client.force_login(other)
    response = getattr(api_client, method)(
        f"{RECS}/{recs['django'].pk}/{suffix}", {"action": "viewed"}, format="json"
    )
    assert response.status_code == 404
    assert not RecommendationFeedback.objects.exists()
    assert not SavedRepository.objects.exists() and not DismissedRepository.objects.exists()
    assert Recommendation.objects.filter(pk=recs["django"].pk).exists()


def test_save_and_unsave_endpoints_and_saved_flag(signed_in_client: APIClient, recs) -> None:
    rec = recs["django"]
    assert signed_in_client.post(f"{RECS}/{rec.pk}/save").json() == {"saved": True}
    assert signed_in_client.get(f"{RECS}/{rec.pk}").json()["saved"] is True
    flags = {r["id"]: r["saved"] for r in signed_in_client.get(RECS).json()["results"]}
    assert flags[rec.pk] is True and flags[recs["plain"].pk] is False
    assert signed_in_client.delete(f"{RECS}/{rec.pk}/save").json() == {"saved": False}
    assert signed_in_client.get(f"{RECS}/{rec.pk}").json()["saved"] is False


def test_saved_flag_is_per_user(api_client: APIClient, user, recs) -> None:
    other = other_user()
    SavedRepository.objects.create(user=other, repository=recs["django"].repository)
    api_client.force_login(user)
    assert api_client.get(f"{RECS}/{recs['django'].pk}").json()["saved"] is False


def test_dismiss_endpoint(signed_in_client: APIClient, recs) -> None:
    rec = recs["django"]
    assert signed_in_client.post(f"{RECS}/{rec.pk}/dismiss").status_code == 204
    ids = [r["id"] for r in signed_in_client.get(RECS).json()["results"]]
    assert rec.pk not in ids
    body = signed_in_client.get("/api/v1/dismissed").json()
    assert body["count"] == 1
    entry = body["results"][0]
    assert entry.keys() == {"repository_id", "repository", "dismissed_at"}
    assert entry["repository"]["full_name"] == "encode/django-tool"


def test_restore_endpoint(signed_in_client: APIClient, user, recs, monkeypatch) -> None:
    monkeypatch.setattr("recommendations.tasks.generate_recommendations.delay", lambda pk: None)
    rec = recs["django"]
    signed_in_client.post(f"{RECS}/{rec.pk}/dismiss")
    response = signed_in_client.delete(f"/api/v1/dismissed/{rec.repository_id}")
    assert response.status_code == 204
    assert signed_in_client.get("/api/v1/dismissed").json()["count"] == 0
    assert signed_in_client.delete(f"/api/v1/dismissed/{rec.repository_id}").status_code == 204


def test_saved_list(signed_in_client: APIClient, user, recs) -> None:
    feedback.save(user, recs["plain"])
    feedback.save(user, recs["django"])
    body = signed_in_client.get("/api/v1/saved").json()
    assert body["count"] == 2
    first = body["results"][0]
    assert first.keys() == {
        "repository_id",
        "repository",
        "saved_at",
        "activity_label",
        "recommendation",
    }
    assert first["repository"]["full_name"] == "encode/django-tool"  # most recent first
    assert first["activity_label"] == "recently_active"
    assert first["recommendation"]["id"] == recs["django"].pk
    assert first["recommendation"]["match_label"] == "strong"
    assert first["recommendation"]["reasons"]
    assert "score" not in first["recommendation"]


def test_saved_list_keeps_no_longer_recommended(signed_in_client: APIClient, user, recs) -> None:
    feedback.save(user, recs["django"])
    Repository.objects.filter(pk=recs["django"].repository_id).update(is_eligible=False)
    generate(user)
    assert not Recommendation.objects.filter(repository=recs["django"].repository).exists()
    entry = signed_in_client.get("/api/v1/saved").json()["results"][0]
    assert entry["repository"]["full_name"] == "encode/django-tool"
    assert entry["recommendation"] is None
    assert signed_in_client.delete(f"/api/v1/saved/{entry['repository_id']}").status_code == 204
    assert signed_in_client.get("/api/v1/saved").json()["count"] == 0
    assert events(user, "unsaved").get().recommendation is None


def test_saved_list_shows_only_own_saves(api_client: APIClient, user, recs) -> None:
    SavedRepository.objects.create(user=other_user(), repository=recs["django"].repository)
    api_client.force_login(user)
    assert api_client.get("/api/v1/saved").json()["count"] == 0


def test_list_query_count_is_constant(signed_in_client: APIClient, user, recs, pool) -> None:  # noqa: F811
    signed_in_client.get(RECS)  # warm up session and content types
    with CaptureQueriesContext(connection) as few:
        signed_in_client.get(RECS)
    feedback.save(user, recs["django"])
    extra = ready_repo(50, "extra/django-app", topics=("django",), deps=("django",))
    add_candidate(recs["django"].developer, extra)
    generate(user)
    feedback.save(user, Recommendation.objects.get(repository=extra))
    with CaptureQueriesContext(connection) as more:
        signed_in_client.get(RECS)
    assert len(more) == len(few)


def test_saved_list_query_count_is_constant(signed_in_client: APIClient, user, recs) -> None:
    feedback.save(user, recs["django"])
    signed_in_client.get("/api/v1/saved")
    with CaptureQueriesContext(connection) as one:
        signed_in_client.get("/api/v1/saved")
    feedback.save(user, recs["plain"])
    with CaptureQueriesContext(connection) as two:
        signed_in_client.get("/api/v1/saved")
    assert len(two) == len(one)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "{recs}/{pk}/feedback"),
        ("post", "{recs}/{pk}/save"),
        ("delete", "{recs}/{pk}/save"),
        ("post", "{recs}/{pk}/dismiss"),
        ("delete", "/api/v1/saved/{repo}"),
        ("delete", "/api/v1/dismissed/{repo}"),
    ],
)
def test_writes_require_csrf(user, recs, method: str, path: str) -> None:
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    rec = recs["django"]
    url = path.format(recs=RECS, pk=rec.pk, repo=rec.repository_id)
    response = getattr(client, method)(url, {"action": "viewed"}, content_type="application/json")
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", f"{RECS}/1/feedback"),
        ("post", f"{RECS}/1/save"),
        ("post", f"{RECS}/1/dismiss"),
        ("get", "/api/v1/saved"),
        ("delete", "/api/v1/saved/1"),
        ("get", "/api/v1/dismissed"),
        ("delete", "/api/v1/dismissed/1"),
    ],
)
def test_signed_out_is_401(api_client: APIClient, method: str, path: str) -> None:
    assert getattr(api_client, method)(path).status_code == 401
