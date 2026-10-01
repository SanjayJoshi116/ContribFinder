from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from developers.models import DeveloperProfile
from repositories.models import ActivityLabel, Repository
from services.ranking import config


class MatchLabel(models.TextChoices):
    STRONG = "strong"
    GOOD = "good"
    PARTIAL = "partial"


class RepositorySize(models.TextChoices):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    UNKNOWN = "unknown"


class ReasonType(models.TextChoices):
    SKILL = "skill"
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    INTEREST = "interest"
    ACTIVITY = "activity"
    OPENNESS = "openness"


class ScoringConfig(models.Model):
    """A versioned set of signal weights and parameters (FR-REC-004). A version always means
    the same numbers: change them by creating a new version, not by editing one in use."""

    version = models.SlugField(max_length=64, unique=True)
    description = models.TextField(blank=True)
    weights = models.JSONField()
    params = models.JSONField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=Q(is_active=True), name="one_active_scoring_config"
            )
        ]

    def __str__(self) -> str:
        return self.version

    def clean(self) -> None:
        if errors := config.validate(self.weights, self.params):
            raise ValidationError(errors)


class Recommendation(models.Model):
    """A ranked candidate repository for a developer (FR-REC-002). Upserted per developer and
    repository so its id survives regenerations; ``score`` and ``signal_scores`` are internal."""

    developer = models.ForeignKey(
        DeveloperProfile, on_delete=models.CASCADE, related_name="recommendations"
    )
    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="recommendations"
    )
    scoring_config = models.ForeignKey(
        ScoringConfig, on_delete=models.PROTECT, related_name="recommendations"
    )
    score = models.FloatField()
    signal_scores = models.JSONField(default=dict)
    rank = models.PositiveIntegerField()
    match_label = models.CharField(max_length=10, choices=MatchLabel.choices)
    # Snapshots taken at generation, so list filters need no recomputation.
    technologies = models.JSONField(default=list, blank=True)
    activity_label = models.CharField(
        max_length=20, choices=ActivityLabel.choices, blank=True
    )  # "" when the repository has no activity snapshot
    size = models.CharField(max_length=10, choices=RepositorySize.choices)
    generated_at = models.DateTimeField()

    class Meta:
        ordering = ["developer", "rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["developer", "repository"], name="unique_developer_recommendation"
            )
        ]
        indexes = [models.Index(fields=["developer", "rank"], name="recommendation_rank_idx")]

    def __str__(self) -> str:
        return f"Recommendation({self.repository_id} for {self.developer_id}, #{self.rank})"


class RecommendationReason(models.Model):
    """Why a recommendation matches, built only from a non-zero signal's evidence (FR-REC-003)."""

    recommendation = models.ForeignKey(
        Recommendation, on_delete=models.CASCADE, related_name="reasons"
    )
    type = models.CharField(max_length=20, choices=ReasonType.choices)
    text = models.CharField(max_length=500)
    weight = models.FloatField()
    detail = models.JSONField(default=dict, blank=True)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["recommendation", "position"]

    def __str__(self) -> str:
        return f"{self.type}: {self.text}"
