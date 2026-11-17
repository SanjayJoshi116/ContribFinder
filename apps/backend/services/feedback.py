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


class IssueNotRelevant(Exception):
    """``opened_issue`` named an issue that is not one of the recommendation's relevant issues
    (checked under the recommendation lock)."""


def _current_recommendation(user: User, repository_id: int) -> Recommendation | None:
    """The user's recommendation of the repository now, with what an event snapshots."""
    return (
        Recommendation.objects.filter(developer__user=user, repository_id=repository_id)
        .select_related("repository", "scoring_config")
        .first()
    )


def _current(user: User, recommendation_id: int, *, lock: bool = False) -> Recommendation | None:
    """The user's recommendation as stored now, with what an event snapshots; None when it is
    gone or another user's. ``lock`` takes its row lock (and only its row)."""
    rows = Recommendation.objects.select_related("repository", "scoring_config")
    if lock:
        rows = rows.select_for_update(of=("self",))
    return rows.filter(pk=recommendation_id, developer__user=user).first()


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


def record(user: User, recommendation_id: int, action: str, *, issue_id: int | None = None) -> bool:
    """Record an event with a snapshot of the recommendation (and, for ``opened_issue``, of
    the issue ``issue_id``). A ``viewed`` event within ``FEEDBACK_VIEW_DEDUP_MINUTES`` of the
    previous one is skipped. Returns whether an event was stored: not when the recommendation
    is gone, nor when the issue is no longer one of its relevant issues (a refresh closed it, a
    generation dropped it). Raises ``IssueNotRelevant`` for an issue of another repository,
    which was never relevant to this recommendation."""
    with transaction.atomic():
        # Only this recommendation's row: views of one recommendation check and insert in
        # turn, without waiting for a generation's whole write. A recommendation deleted
        # meanwhile (regenerated away, dismissed) gets no event: it would reference no row.
        # The snapshot comes from the locked row; the caller passes only its id.
        current = _current(user, recommendation_id, lock=True)
        if current is None:
            return False
        issue = None
        if issue_id is not None:
            # Then the issue (services/locks.py order), so no refresh deletes it before the
            # event references it; only while it is one of this recommendation's relevant
            # issues. A generation rewrites those while it holds this recommendation's lock,
            # so the set read here is the one the event belongs to (FB-1).
            issue = (
                Issue.objects.select_for_update(of=("self",))
                .filter(pk=issue_id, recommendations__recommendation=current)
                .first()
            )
            if issue is None:
                # Dropped or closed since the page loaded: a race, like a recommendation gone
                # meanwhile, so no event and no error. Another repository's issue never was.
                if (
                    Issue.objects.filter(pk=issue_id)
                    .exclude(repository_id=current.repository_id)
                    .exists()
                ):
                    raise IssueNotRelevant
                return False
        if action == FeedbackAction.VIEWED:
            since = timezone.now() - timedelta(minutes=settings.FEEDBACK_VIEW_DEDUP_MINUTES)
            if RecommendationFeedback.objects.filter(
                user=user,
                recommendation=current,
                action=FeedbackAction.VIEWED,
                created_at__gte=since,
            ).exists():
                return False
        _event(user, current.repository, current, action, issue)
    return True


def save(user: User, recommendation_id: int) -> SavedRepository:
    """Idempotent: saving twice keeps the first save time and records one event. Raises
    ``Recommendation.DoesNotExist`` when the recommendation is gone (dismissed or regenerated
    away) by the time the lock is held: a dismissed repository is never saved."""
    with transaction.atomic():
        lock_developer(user.pk)
        # Read under the profile lock (a generation writes under it too): the snapshot is the
        # row as it is now.
        current = _current(user, recommendation_id)
        if (
            current is None
            or DismissedRepository.objects.filter(
                user=user, repository_id=current.repository_id
            ).exists()
        ):
            raise Recommendation.DoesNotExist()
        saved, created = SavedRepository.objects.get_or_create(
            user=user, repository=current.repository
        )
        if created:
            _event(user, current.repository, current, FeedbackAction.SAVED)
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
                user,
                repository,
                _current_recommendation(user, repository_id),
                FeedbackAction.UNSAVED,
            )
    return bool(deleted)


def dismiss(user: User, repository_id: int, reason: str = "") -> None:
    """Hide the repository from this and every later generation, and unsave it (recorded as
    ``unsaved``). The optional ``reason`` (a ``DismissReason``) is stored on the hidden entry
    and its ``dismissed`` event; an already hidden repository keeps its stored reason."""
    with transaction.atomic():
        lock_developer(user.pk)
        # A generation may have dropped it before the lock was ours: the dismissal still
        # holds, but the events must not reference the deleted row. The repository comes from
        # this read (the caller passes only its id).
        current = _current_recommendation(user, repository_id)
        repository = (
            current.repository
            if current is not None
            else Repository.objects.filter(pk=repository_id).first()
        )
        if repository is None:
            # Deleted meanwhile with the user's data (delete-data, orphan cleanup): nothing
            # left to hide; the view answers 404, as for any recommendation gone.
            raise Recommendation.DoesNotExist()
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
