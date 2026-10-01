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
    repository_full_name = models.CharField(max_length=255)
    action = models.CharField(max_length=20, choices=FeedbackAction.choices)
    # Snapshot of the recommendation at the time; blank/null when there was none.
    match_label = models.CharField(max_length=10, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    config_version = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "recommendation", "action", "-created_at"],
                name="feedback_dedup_idx",
            )
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

    def __str__(self) -> str:
        return f"SavedRepository({self.repository_id} by {self.user_id})"


class DismissedRepository(models.Model):
    """A repository the user hid (FR-FEEDBACK-003); excluded from every later ranking run."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dismissed_repositories"
    )
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="dismissals")
    dismissed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-dismissed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "repository"], name="unique_dismissed_repository"
            )
        ]

    def __str__(self) -> str:
        return f"DismissedRepository({self.repository_id} by {self.user_id})"
