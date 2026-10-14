"""Feedback events, save and dismiss (spec: recommendation-feedback; design D2).

Feedback is recorded for analytics and evaluation only: nothing here changes scores or ranking.
Saves and dismissals are current state; dismissals are honored by every later generation
(``load_candidates`` and ``RecommendationService._persist``).
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from feedback.models import (
    DismissedRepository,
    FeedbackAction,
    RecommendationFeedback,
    SavedRepository,
)
from issues.models import Issue
from recommendations.models import Recommendation
from repositories.models import Repository

from . import jobs

# Actions a client may post directly; the others are recorded by save and dismiss.
CLIENT_ACTIONS = (
    FeedbackAction.VIEWED,
    FeedbackAction.OPENED_REPOSITORY,
    FeedbackAction.OPENED_ISSUE,
)


def _current_recommendation(user: User, repository: Repository) -> Recommendation | None:
    return (
        Recommendation.objects.filter(developer__user=user, repository=repository)
        .select_related("scoring_config")
        .first()
    )


def _event(
    user: User,
    repository: Repository,
    recommendation: Recommendation | None,
    action: str,
    issue: Issue | None = None,
) -> RecommendationFeedback:
    return RecommendationFeedback.objects.create(
        user=user,
        repository=repository,
        recommendation=recommendation,
        repository_full_name=repository.full_name,
        action=action,
        issue=issue,
        issue_number=issue.number if issue else None,
        match_label=recommendation.match_label if recommendation else "",
        rank=recommendation.rank if recommendation else None,
        config_version=recommendation.scoring_config.version if recommendation else "",
    )


def record(
    user: User, recommendation: Recommendation, action: str, *, issue: Issue | None = None
) -> bool:
    """Record an event with a snapshot of the recommendation (and, for ``opened_issue``, of
    the issue; the caller checks it is one of the recommendation's relevant issues). A
    ``viewed`` event within ``FEEDBACK_VIEW_DEDUP_MINUTES`` of the previous one is skipped.
    Returns whether an event was stored."""
    if action == FeedbackAction.VIEWED:
        since = timezone.now() - timedelta(minutes=settings.FEEDBACK_VIEW_DEDUP_MINUTES)
        if RecommendationFeedback.objects.filter(
            user=user,
            recommendation=recommendation,
            action=FeedbackAction.VIEWED,
            created_at__gte=since,
        ).exists():
            return False
    _event(user, recommendation.repository, recommendation, action, issue)
    return True


def save(user: User, recommendation: Recommendation) -> SavedRepository:
    """Idempotent: saving twice keeps the first save time and records one event."""
    with transaction.atomic():
        saved, created = SavedRepository.objects.get_or_create(
            user=user, repository=recommendation.repository
        )
        if created:
            _event(user, recommendation.repository, recommendation, FeedbackAction.SAVED)
    return saved


def unsave(user: User, repository_id: int) -> bool:
    """Unsave whether or not the repository is still recommended. Returns whether it was
    saved."""
    with transaction.atomic():
        deleted, _ = SavedRepository.objects.filter(user=user, repository_id=repository_id).delete()
        if deleted:
            repository = Repository.objects.get(pk=repository_id)
            _event(
                user, repository, _current_recommendation(user, repository), FeedbackAction.UNSAVED
            )
    return bool(deleted)


def dismiss(user: User, recommendation: Recommendation) -> None:
    """Hide the repository from this and every later generation, and unsave it."""
    repository = recommendation.repository
    with transaction.atomic():
        _, created = DismissedRepository.objects.get_or_create(user=user, repository=repository)
        if created:
            _event(user, repository, recommendation, FeedbackAction.DISMISSED)
        SavedRepository.objects.filter(user=user, repository=repository).delete()
        recommendation.delete()


def restore(user: User, repository_id: int) -> bool:
    """Undo a dismissal and start a generation so the repository can come back. Returns
    whether it was dismissed."""
    with transaction.atomic():
        deleted, _ = DismissedRepository.objects.filter(
            user=user, repository_id=repository_id
        ).delete()
        if deleted:
            repository = Repository.objects.get(pk=repository_id)
            _event(user, repository, None, FeedbackAction.UNDISMISSED)
    if deleted:
        jobs.start_recommendations(user)
    return bool(deleted)
