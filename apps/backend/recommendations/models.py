import json
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from developers.models import DeveloperProfile
from repositories.models import ActivityLabel, Repository
from services.ranking import config
from services.text import join_names


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
    ISSUE_AVAILABILITY = "issue_availability"
    DIFFICULTY = "difficulty"


class ImmutableConfig(ValidationError):
    """A stored configuration's version, weights or params were changed."""


class ScoringConfig(models.Model):
    """A versioned set of signal weights and parameters (FR-REC-004). A version always means
    the same numbers: once stored, version, weights and params never change (``save`` refuses
    it); new numbers need a new version. ``is_active`` and ``description`` stay writable."""

    FIXED_FIELDS = ("version", "weights", "params")

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

    def save(self, *args: Any, **kwargs: Any) -> None:
        update_fields = kwargs.get("update_fields")
        touches_fixed = update_fields is None or set(update_fields) & set(self.FIXED_FIELDS)
        if not self._state.adding and touches_fixed:
            stored = ScoringConfig.objects.filter(pk=self.pk).values(*self.FIXED_FIELDS).first()
            # Compared as stored: a tuple reads back as a list and is not a change.
            changed = stored and [
                f
                for f in self.FIXED_FIELDS
                if stored[f] != json.loads(json.dumps(getattr(self, f)))
            ]
            if changed:
                raise ImmutableConfig(
                    f"A stored scoring configuration cannot change its {join_names(changed)}; "
                    "create a new version instead."
                )
        super().save(*args, **kwargs)

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
    relevant_issue_count = models.PositiveSmallIntegerField(default=0)
    issue_difficulties = models.JSONField(default=list, blank=True)  # distinct values
    issue_contribution_types = models.JSONField(default=list, blank=True)  # distinct values
    generated_at = models.DateTimeField()

    class Meta:
        ordering = ["developer", "rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["developer", "repository"], name="unique_developer_recommendation"
            ),
            # Ranks start at 1; a positive field alone would store 0 (T-12).
            models.CheckConstraint(condition=Q(rank__gte=1), name="recommendation_rank_positive"),
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
