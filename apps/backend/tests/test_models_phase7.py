"""Issue data model (Phase 7, group 1)."""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from developers.models import DeveloperProfile
from feedback.models import RecommendationFeedback
from issues.models import Issue, RecommendedIssue
from services.data_deletion import delete_github_data

from .repo_fixtures import add_candidate, make_candidate_repo, make_issue
from .test_models_phase5 import make_recommendation

pytestmark = pytest.mark.django_db


@pytest.fixture
def profile(user) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


def test_issue_defaults_are_unknown() -> None:
    issue = make_issue(make_candidate_repo(1), 5)
    assert (issue.contribution_type, issue.difficulty) == ("unknown", "unknown")
    assert issue.labels == [] and issue.technologies == []


def test_unique_github_id() -> None:
    issue = make_issue(make_candidate_repo(1), 5)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_issue(make_candidate_repo(2), 6, github_id=issue.github_id)


def test_unique_number_per_repository() -> None:
    repo = make_candidate_repo(1)
    make_issue(repo, 5)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_issue(repo, 5, github_id=999)
    make_issue(make_candidate_repo(2), 5)  # another repository may reuse the number


def test_unique_recommended_issue(profile) -> None:
    repo = make_candidate_repo(1)
    rec = make_recommendation(profile, repo)
    issue = make_issue(repo, 5)
    RecommendedIssue.objects.create(recommendation=rec, issue=issue, rank=1, score=0.5)
    with pytest.raises(IntegrityError), transaction.atomic():
        RecommendedIssue.objects.create(recommendation=rec, issue=issue, rank=2, score=0.4)


def test_issues_cascade_with_repository() -> None:
    repo = make_candidate_repo(1)
    make_issue(repo, 5)
    repo.delete()
    assert not Issue.objects.exists()


def test_issues_of_orphaned_repository_deleted_with_user_data(user, profile) -> None:
    repo = make_candidate_repo(1)
    add_candidate(profile, repo)
    make_issue(repo, 5)
    delete_github_data(user)
    assert not Issue.objects.exists()


def test_recommended_issues_cascade_with_recommendation(profile) -> None:
    repo = make_candidate_repo(1)
    rec = make_recommendation(profile, repo)
    issue = make_issue(repo, 5)
    RecommendedIssue.objects.create(recommendation=rec, issue=issue, rank=1, score=0.5)
    rec.delete()
    assert not RecommendedIssue.objects.exists()
    assert Issue.objects.filter(pk=issue.pk).exists()  # shared data stays


def test_feedback_keeps_snapshot_when_issue_deleted(user, profile) -> None:
    repo = make_candidate_repo(1)
    rec = make_recommendation(profile, repo)
    issue = make_issue(repo, 5)
    event = RecommendationFeedback.objects.create(
        user=user,
        repository=repo,
        recommendation=rec,
        repository_full_name=repo.full_name,
        action="opened_issue",
        issue=issue,
        issue_number=issue.number,
    )
    issue.delete()
    event.refresh_from_db()
    assert event.issue is None
    assert event.issue_number == 5
    assert event.recommendation == rec
