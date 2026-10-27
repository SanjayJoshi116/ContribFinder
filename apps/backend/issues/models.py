from django.db import models

from developers.models import IssueDifficulty

# Shared with the developer profile's preferred issue difficulty: one choice set.
Difficulty = IssueDifficulty


class ContributionType(models.TextChoices):
    CODE = "code"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    DEVOPS = "devops"
    DESIGN = "design"
    UNKNOWN = "unknown"


class Issue(models.Model):
    """An open GitHub issue of a pooled repository (FR-ISSUE-001), stored once and shared by
    every developer. The fetched set replaces the stored one on each refresh; analysis fields
    (FR-ISSUE-002 to 004) are recomputed with every fetch."""

    repository = models.ForeignKey(
        "repositories.Repository", on_delete=models.CASCADE, related_name="issues"
    )
    github_id = models.BigIntegerField(unique=True)
    number = models.PositiveIntegerField()

    # From GitHub. ``body`` is plain text, capped at ISSUE_BODY_MAX_CHARS.
    title = models.CharField(max_length=1024)
    body = models.TextField(blank=True)
    raw_labels = models.JSONField(default=list, blank=True)
    state = models.CharField(max_length=20, default="open")
    is_locked = models.BooleanField(default=False)
    has_assignee = models.BooleanField(default=False)
    comments = models.PositiveIntegerField(default=0)
    html_url = models.URLField(max_length=500)
    github_created_at = models.DateTimeField(null=True, blank=True)
    github_updated_at = models.DateTimeField(null=True, blank=True)

    # ContribFinder analysis, each with the evidence that decided it.
    labels = models.JSONField(default=list, blank=True)
    contribution_type = models.CharField(
        max_length=20, choices=ContributionType.choices, default=ContributionType.UNKNOWN
    )
    contribution_type_evidence = models.JSONField(default=dict, blank=True)
    difficulty = models.CharField(
        max_length=20, choices=Difficulty.choices, default=Difficulty.UNKNOWN
    )
    difficulty_evidence = models.JSONField(default=dict, blank=True)
    technologies = models.JSONField(default=list, blank=True)  # [{slug, source}]
    analyzed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["repository", "-github_updated_at", "number"]
        constraints = [
            models.UniqueConstraint(fields=["repository", "number"], name="unique_repo_issue")
        ]
        indexes = [models.Index(fields=["repository", "-github_updated_at"])]

    def __str__(self) -> str:
        return f"{self.repository_id}#{self.number}"


class RecommendedIssue(models.Model):
    """A relevant issue of a recommendation (FR-ISSUE-005). Rebuilt with its recommendation;
    ``score`` is internal ranking data and never serialized."""

    recommendation = models.ForeignKey(
        "recommendations.Recommendation",
        on_delete=models.CASCADE,
        related_name="recommended_issues",
    )
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="recommendations")
    rank = models.PositiveSmallIntegerField()
    score = models.FloatField()
    reasons = models.JSONField(default=list, blank=True)  # [{type, text, detail}]

    class Meta:
        ordering = ["recommendation", "rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["recommendation", "issue"], name="unique_recommended_issue"
            ),
            models.CheckConstraint(
                condition=models.Q(rank__gte=1), name="recommended_issue_rank_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"RecommendedIssue({self.issue_id} for {self.recommendation_id}, #{self.rank})"
