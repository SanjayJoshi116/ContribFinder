from django.conf import settings
from django.db import models

from recommendations.models import Recommendation
from repositories.models import Repository


class FeedbackAction(models.TextChoices):
    VIEWED = "viewed"
    SAVED = "saved"
    UNSAVED = "unsaved"
    DISMISSED = "dismissed"
    UNDISMISSED = "undismissed"
    OPENED_REPOSITORY = "opened_repository"
    OPENED_ISSUE = "opened_issue"


# Actions that change the saved or hidden list (restore records ``undismissed``).
LIST_ACTIONS = (
    FeedbackAction.SAVED,
    FeedbackAction.UNSAVED,
    FeedbackAction.DISMISSED,
    FeedbackAction.UNDISMISSED,
)


class DismissReason(models.TextChoices):
    """Why a user hid a repository: optional, recorded and reported, never scored."""

    NOT_MY_STACK = "not_my_stack", "Not my stack"
    TOO_BIG = "too_big", "Too big"
    INACTIVE = "inactive", "Inactive"
    ALREADY_KNOW = "already_know", "Already know it"


class RecommendationFeedback(models.Model):
    """An interaction with a recommendation (FR-FEEDBACK-001, -004). Stored independently of the
    recommendation: the snapshot fields keep an event meaningful after regenerations, and the
    foreign keys are nulled rather than deleting the event. Analytics only, never ranking."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendation_feedback"
    )
    repository = models.ForeignKey(
        Repository, null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback"
    )
    recommendation = models.ForeignKey(
        Recommendation, null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback"
    )
    # opened_issue only: the issue (nulled when it is closed or removed) and its number.
    issue = models.ForeignKey(
        "issues.Issue", null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback"
    )
    issue_number = models.PositiveIntegerField(null=True, blank=True)
    repository_full_name = models.CharField(max_length=255)
    action = models.CharField(max_length=20, choices=FeedbackAction.choices)
    # Snapshot of the recommendation at the time; blank/null when there was none.
    match_label = models.CharField(max_length=10, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    config_version = models.CharField(max_length=64, blank=True)
    # dismissed only: the reason the user gave, blank when none.
    dismiss_reason = models.CharField(
        max_length=20, choices=DismissReason.choices, blank=True, default=""
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Null when there was no recommendation; never 0 (T-12).
            models.CheckConstraint(
                condition=models.Q(rank__isnull=True) | models.Q(rank__gte=1),
                name="feedback_rank_positive",
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "recommendation", "action", "-created_at"],
                name="feedback_dedup_idx",
            ),
            # The data version's latest list change (services.data_versions), without reading
            # every ``viewed`` event.
            models.Index(
                fields=["user", "-created_at"],
                condition=models.Q(action__in=LIST_ACTIONS),
                name="feedback_list_change_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.action}:{self.repository_full_name}"


class SavedRepository(models.Model):
    """A repository the user kept (FR-FEEDBACK-002); survives regenerations."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_repositories"
    )
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="saves")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-saved_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "repository"], name="unique_saved_repository")
        ]
        # The saved list's keyset order (SavedPagination): an ordered index scan per page.
        indexes = [models.Index(fields=["user", "-saved_at", "-id"], name="saved_keyset_idx")]

    def __str__(self) -> str:
        return f"SavedRepository({self.repository_id} by {self.user_id})"


class DismissedRepository(models.Model):
    """A repository the user hid (FR-FEEDBACK-003); excluded from every later ranking run."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dismissed_repositories"
    )
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="dismissals")
    reason = models.CharField(max_length=20, choices=DismissReason.choices, blank=True, default="")
    dismissed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-dismissed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "repository"], name="unique_dismissed_repository"
            )
        ]
        indexes = [
            models.Index(fields=["user", "-dismissed_at", "-id"], name="dismissed_keyset_idx")
        ]

    def __str__(self) -> str:
        return f"DismissedRepository({self.repository_id} by {self.user_id})"
