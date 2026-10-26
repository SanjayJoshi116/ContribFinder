"""Feedback events, save and dismiss (spec: recommendation-feedback; design D2).

Feedback is recorded for analytics and evaluation only: nothing here changes scores or ranking.
Saves and dismissals are current state; dismissals are honored by every later generation
(``load_candidates`` and ``RecommendationService._persist``). Every write here locks the
developer profile first (``services.locks``), the order a generation's write uses too.
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
from .locks import lock_developer

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
    dismiss_reason: str = "",
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
        dismiss_reason=dismiss_reason,
    )


def record(
    user: User, recommendation: Recommendation, action: str, *, issue: Issue | None = None
) -> bool:
    """Record an event with a snapshot of the recommendation (and, for ``opened_issue``, of
    the issue; the caller checks it is one of the recommendation's relevant issues). A
    ``viewed`` event within ``FEEDBACK_VIEW_DEDUP_MINUTES`` of the previous one is skipped.
    Returns whether an event was stored (not when the recommendation is gone)."""
    with transaction.atomic():
        # Only this recommendation's row: views of one recommendation check and insert in
        # turn, without waiting for a generation's whole write. A recommendation deleted
        # meanwhile (regenerated away, dismissed) gets no event: it would reference no row.
        if not Recommendation.objects.select_for_update().filter(pk=recommendation.pk).exists():
            return False
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
    """Idempotent: saving twice keeps the first save time and records one event. Raises
    ``Recommendation.DoesNotExist`` when the recommendation is gone (dismissed or regenerated
    away) by the time the lock is held: a dismissed repository is never saved."""
    with transaction.atomic():
        lock_developer(user.pk)
        gone = not Recommendation.objects.filter(pk=recommendation.pk).exists()
        if (
            gone
            or DismissedRepository.objects.filter(
                user=user, repository_id=recommendation.repository_id
            ).exists()
        ):
            raise Recommendation.DoesNotExist()
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
        lock_developer(user.pk)
        deleted, _ = SavedRepository.objects.filter(user=user, repository_id=repository_id).delete()
        if deleted:
            repository = Repository.objects.get(pk=repository_id)
            _event(
                user, repository, _current_recommendation(user, repository), FeedbackAction.UNSAVED
            )
    return bool(deleted)


def dismiss(user: User, recommendation: Recommendation, reason: str = "") -> None:
    """Hide the repository from this and every later generation, and unsave it (recorded as
    ``unsaved``). The optional ``reason`` (a ``DismissReason``) is stored on the hidden entry
    and its ``dismissed`` event; an already hidden repository keeps its stored reason."""
    repository = recommendation.repository
    with transaction.atomic():
        lock_developer(user.pk)
        # A generation may have dropped it before the lock was ours: the dismissal still
        # holds, but the events must not reference the deleted row.
        current = _current_recommendation(user, repository)
        _, created = DismissedRepository.objects.get_or_create(
            user=user, repository=repository, defaults={"reason": reason}
        )
        if created:
            _event(user, repository, current, FeedbackAction.DISMISSED, dismiss_reason=reason)
        unsaved, _ = SavedRepository.objects.filter(user=user, repository=repository).delete()
        if unsaved:
            _event(user, repository, current, FeedbackAction.UNSAVED)
        if current is not None:
            current.delete()


def restore(user: User, repository_id: int) -> bool:
    """Undo a dismissal and start a generation so the repository can come back. Returns
    whether it was dismissed."""
    with transaction.atomic():
        lock_developer(user.pk)
        deleted, _ = DismissedRepository.objects.filter(
            user=user, repository_id=repository_id
        ).delete()
        if deleted:
            repository = Repository.objects.get(pk=repository_id)
            _event(user, repository, None, FeedbackAction.UNDISMISSED)
    if deleted:
        jobs.start_recommendations(user)
    return bool(deleted)
