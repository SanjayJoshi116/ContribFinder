from django.conf import settings
from django.db import models


class Repository(models.Model):
    """A GitHub repository, stored once and shared by every user linked to it (and, from
    Phase 4, by discovery candidates)."""

    github_id = models.BigIntegerField(unique=True)
    owner_login = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=511, unique=True)
    description = models.TextField(blank=True)
    html_url = models.URLField(max_length=500)
    default_branch = models.CharField(max_length=255, blank=True)
    stars = models.PositiveIntegerField(default=0)
    forks = models.PositiveIntegerField(default=0)
    open_issues = models.PositiveIntegerField(default=0)
    primary_language = models.CharField(max_length=100, blank=True)
    license_spdx = models.CharField(max_length=100, blank=True)
    is_fork = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    github_created_at = models.DateTimeField(null=True, blank=True)
    github_updated_at = models.DateTimeField(null=True, blank=True)
    pushed_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField()

    class Meta:
        verbose_name_plural = "repositories"
        indexes = [models.Index(fields=["-pushed_at"])]

    def __str__(self) -> str:
        return self.full_name


class RepositoryLanguage(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="languages")
    language = models.CharField(max_length=100)
    bytes = models.PositiveBigIntegerField()

    class Meta:
        ordering = ["-bytes"]
        constraints = [
            models.UniqueConstraint(fields=["repository", "language"], name="unique_repo_language")
        ]

    def __str__(self) -> str:
        return f"{self.repository_id}:{self.language}"


class RepositoryTopic(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="topics")
    topic = models.CharField(max_length=100)

    class Meta:
        ordering = ["topic"]
        constraints = [
            models.UniqueConstraint(fields=["repository", "topic"], name="unique_repo_topic")
        ]

    def __str__(self) -> str:
        return f"{self.repository_id}:{self.topic}"


class UserRepository(models.Model):
    """Links a user to a repository they own (later: contributed to, starred, ...)."""

    class Relation(models.TextChoices):
        OWNER = "owner"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="repository_links"
    )
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="user_links")
    relation = models.CharField(max_length=20, choices=Relation.choices, default=Relation.OWNER)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "repository", "relation"], name="unique_user_repository_relation"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}->{self.repository_id} ({self.relation})"
