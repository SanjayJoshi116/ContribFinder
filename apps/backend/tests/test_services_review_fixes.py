"""Service fixes from the review sweep (Bug_Backlog.md batch 31, change services-review-fixes)."""

from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import caches
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from developers.models import DeveloperProfile
from e2e.builders import make_candidate_repo, make_issue
from feedback.models import RecommendationFeedback
from jobs.models import SyncJob
from recommendations.models import Recommendation
from recommendations.tasks import generate_recommendations
from repositories.models import Repository, UserRepository
from services import data_deletion, feedback, jobs
from services.data_versions import versions
from services.errors import JobCancelled, PermanentJobError
from services.github.errors import GitHubTransientError
from services.ranking.service import RecommendationService

from .factories import GitHubAccountFactory
from .shared_fixtures import developer  # noqa: F401 - pytest fixture
from .test_models_phase5 import make_recommendation

pytestmark = pytest.mark.django_db


def linked_repo(user: User, github_id: int) -> Repository:
    repo = make_candidate_repo(github_id)
    UserRepository.objects.create(user=user, repository=repo)
    return repo


# --- Data deletion (SVC-1, SVC-3, SVC-6, SVC-10) ----------------------------------------


def test_account_deletion_purges_the_users_github_cache(
    signed_in_client: APIClient, user: User, django_capture_on_commit_callbacks
) -> None:
    cache = caches["default"]
    key = f"github:etag:{user.pk}:https://api.github.com/user"
    cache.set(key, {"etag": "x"})
    with patch("github.tasks.revoke_later.delay"), django_capture_on_commit_callbacks(execute=True):
        response = signed_in_client.delete("/api/v1/auth/account")
    assert response.status_code == 204
    assert cache.get(key) is None  # purged by the id, not by the deleted user's pk (None)


def test_a_second_purge_is_queued_after_workers_stop(
    user: User, django_capture_on_commit_callbacks
) -> None:
    with (
        patch("github.tasks.purge_user_cache.apply_async") as later,
        django_capture_on_commit_callbacks(execute=True),
    ):
        data_deletion.delete_github_data(user)
    later.assert_called_once_with((user.pk,), countdown=settings.SYNC_STALE_AFTER_SECONDS)


def test_a_broker_error_never_fails_the_deletion(
    signed_in_client: APIClient, user: User, django_capture_on_commit_callbacks
) -> None:
    linked_repo(user, 1)
    with (
        patch("github.tasks.purge_user_cache.apply_async", side_effect=ConnectionError("down")),
        django_capture_on_commit_callbacks(execute=True),
    ):
        response = signed_in_client.delete("/api/v1/profile/github-data")
    assert response.status_code == 204
    assert not UserRepository.objects.filter(user=user).exists()


def test_orphans_are_counted_from_the_delete(user: User) -> None:
    linked_repo(user, 1)
    shared = linked_repo(user, 2)
    other = GitHubAccountFactory.create().user
    UserRepository.objects.create(user=other, repository=shared)

    counts = data_deletion.delete_github_data(user)

    assert counts["repositories"] == 1
    assert list(Repository.objects.values_list("github_id", flat=True)) == [2]


# --- Jobs (SVC-4, SVC-5, SVC-8) ---------------------------------------------------------


def generation(user: User) -> SyncJob:
    return jobs.new_job(user, jobs.RECOMMENDATIONS)


def run_requesting_a_rerun(monkeypatch: pytest.MonkeyPatch, user: User, error: Exception) -> None:
    def run(self: RecommendationService) -> None:
        jobs.start_recommendations(user)  # e.g. a restore while this job is RUNNING
        raise error

    monkeypatch.setattr(RecommendationService, "run", run)


def test_a_rerun_request_survives_a_failed_generation(user, developer, monkeypatch) -> None:
    job = generation(user)
    run_requesting_a_rerun(monkeypatch, user, PermanentJobError("broken"))
    generate_recommendations.delay(job.pk)
    job.refresh_from_db()
    assert job.status == "FAILED" and job.rerun_requested is True
    follow_up = SyncJob.objects.exclude(pk=job.pk).get(user=user)
    assert (follow_up.job_type, follow_up.status) == (jobs.RECOMMENDATIONS, "PENDING")


def test_a_cancelled_generation_starts_no_rerun(user, developer, monkeypatch) -> None:
    job = generation(user)
    run_requesting_a_rerun(monkeypatch, user, JobCancelled())
    generate_recommendations.delay(job.pk)
    assert not SyncJob.objects.exclude(pk=job.pk).filter(user=user).exists()


@override_settings(CELERY_TASK_ALWAYS_EAGER=False)  # with a worker; eager mode never retries
def test_a_retried_generation_starts_no_rerun_yet(user, developer, monkeypatch) -> None:
    job = generation(user)
    run_requesting_a_rerun(monkeypatch, user, GitHubTransientError("GET /x returned 503"))
    monkeypatch.setattr(generate_recommendations, "retry", lambda **kw: RuntimeError("retry"))
    with pytest.raises(RuntimeError, match="retry"):
        generate_recommendations.apply(args=(job.pk,), throw=True)
    job.refresh_from_db()
    assert job.status == "RETRYING"
    assert not SyncJob.objects.exclude(pk=job.pk).filter(user=user).exists()


def test_a_job_deleted_after_its_claim_is_not_claimed(user, monkeypatch) -> None:
    job = generation(user)
    real_select_related = SyncJob.objects.select_related

    def deleted_meanwhile(*fields):  # the reload runs after the claim UPDATE
        SyncJob.objects.filter(pk=job.pk).delete()
        return real_select_related(*fields)

    monkeypatch.setattr(SyncJob.objects, "select_related", deleted_meanwhile)
    assert jobs.claim_job(job.pk) is None


# --- Feedback and data versions (SVC-2, SVC-7, SVC-9) -----------------------------------


@pytest.fixture
def recommendation(user: User) -> Recommendation:
    profile = DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())
    return make_recommendation(profile, make_candidate_repo(1), rank=3)


def test_events_snapshot_the_row_under_the_lock(user: User, recommendation) -> None:
    Recommendation.objects.filter(pk=recommendation.pk).update(rank=7, match_label="strong")
    assert feedback.record(user, recommendation, "viewed")  # loaded before the regeneration
    feedback.save(user, recommendation)
    snapshots = set(RecommendationFeedback.objects.values_list("action", "rank", "match_label"))
    assert snapshots == {("viewed", 7, "strong"), ("saved", 7, "strong")}


def test_an_issue_gone_before_the_lock_stores_no_event(user: User, recommendation) -> None:
    issue = make_issue(recommendation.repository, 1)
    type(issue).objects.filter(pk=issue.pk).delete()  # an issue refresh closed it meanwhile
    assert not feedback.record(user, recommendation, "opened_issue", issue=issue)
    assert not RecommendationFeedback.objects.exists()


def test_a_dismissal_moves_the_recommendations_version(user: User, recommendation) -> None:
    before = versions(user).recommendations
    feedback.dismiss(user, recommendation)
    dismissed = RecommendationFeedback.objects.get(action="dismissed").created_at
    after = versions(user)
    assert after.recommendations == dismissed
    assert before is None or dismissed > before
    assert after.github is None and after.profile is not None
