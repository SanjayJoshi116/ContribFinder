"""Derived developer profile (Phase 3, design D1).

Everything here is computed from stored GitHub data by ``services/profiling`` and replaced
wholesale on each analysis. Raw GitHub data (including the profile README) stays in the
``github`` and ``repositories`` apps.
"""

from django.conf import settings
from django.db import models


class ExperienceLevel(models.TextChoices):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERIENCED = "experienced"
    UNKNOWN = "unknown"


class ProjectSize(models.TextChoices):
    ANY = "any"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class IssueDifficulty(models.TextChoices):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    UNKNOWN = "unknown"


class SkillCategory(models.TextChoices):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    LIBRARY = "library"
    DATABASE = "database"
    CLOUD = "cloud"
    DEVOPS = "devops"
    TOOL = "tool"


class SkillSource(models.TextChoices):
    README = "readme"
    LANGUAGE = "language"
    TOPIC = "topic"
    DEPENDENCY = "dependency"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    REPEATED_CONTRIBUTION = "repeated_contribution"


class InterestSource(models.TextChoices):
    README = "readme"
    REPO_DESCRIPTION = "repo_description"
    TOPIC = "topic"
    CONTRIBUTION = "contribution"


class DeveloperProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="developer_profile"
    )
    summary = models.TextField(blank=True)
    # Internal matching signal only: never serialized to the API (SRS-2 §17).
    experience_level = models.CharField(
        max_length=20, choices=ExperienceLevel.choices, default=ExperienceLevel.UNKNOWN
    )
    experience_signals = models.JSONField(default=dict, blank=True)
    preferred_project_size = models.CharField(
        max_length=20, choices=ProjectSize.choices, default=ProjectSize.ANY
    )
    preferred_issue_difficulty = models.CharField(
        max_length=20, choices=IssueDifficulty.choices, default=IssueDifficulty.UNKNOWN
    )
    # [{name, bytes, share, repo_count}], ordered by bytes.
    languages = models.JSONField(default=list, blank=True)
    # Weights, thresholds and taxonomy version the profile was computed with.
    analysis_config = models.JSONField(default=dict, blank=True)
    analyzed_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"DeveloperProfile(user={self.user_id})"


class Skill(models.Model):
    """Catalog skill, upserted from ``services.profiling.taxonomy`` (the source of truth)."""

    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=SkillCategory.choices)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DeveloperSkill(models.Model):
    profile = models.ForeignKey(DeveloperProfile, on_delete=models.CASCADE, related_name="skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="developer_skills")
    confidence = models.FloatField()
    first_observed_at = models.DateTimeField(null=True, blank=True)
    last_observed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-confidence", "skill__name"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "skill"], name="unique_profile_skill")
        ]

    def __str__(self) -> str:
        return f"{self.profile_id}:{self.skill_id} ({self.confidence:.2f})"


class SkillEvidence(models.Model):
    developer_skill = models.ForeignKey(
        DeveloperSkill, on_delete=models.CASCADE, related_name="evidence"
    )
    source = models.CharField(max_length=30, choices=SkillSource.choices)
    repository = models.ForeignKey(
        "repositories.Repository", on_delete=models.SET_NULL, null=True, blank=True
    )
    detail = models.CharField(max_length=255, blank=True)
    observed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["source", "-observed_at"]
        verbose_name_plural = "skill evidence"

    def __str__(self) -> str:
        return f"{self.developer_skill_id}:{self.source}"


class Interest(models.Model):
    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DeveloperInterest(models.Model):
    profile = models.ForeignKey(
        DeveloperProfile, on_delete=models.CASCADE, related_name="interests"
    )
    interest = models.ForeignKey(
        Interest, on_delete=models.CASCADE, related_name="developer_interests"
    )
    strength = models.FloatField()

    class Meta:
        ordering = ["-strength", "interest__name"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "interest"], name="unique_profile_interest")
        ]

    def __str__(self) -> str:
        return f"{self.profile_id}:{self.interest_id} ({self.strength:.2f})"


class InterestEvidence(models.Model):
    developer_interest = models.ForeignKey(
        DeveloperInterest, on_delete=models.CASCADE, related_name="evidence"
    )
    source = models.CharField(max_length=30, choices=InterestSource.choices)
    repository = models.ForeignKey(
        "repositories.Repository", on_delete=models.SET_NULL, null=True, blank=True
    )
    detail = models.CharField(max_length=255, blank=True)
    observed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["source", "-observed_at"]
        verbose_name_plural = "interest evidence"

    def __str__(self) -> str:
        return f"{self.developer_interest_id}:{self.source}"
