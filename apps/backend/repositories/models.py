from django.conf import settings
from django.db import models
from django.utils import timezone


class Lifecycle(models.TextChoices):
    """Repository processing state (SRS-2 §23). ``EMBEDDED`` arrives in Phase 6."""

    DISCOVERED = "discovered"
    FETCHING = "fetching"
    ANALYZED = "analyzed"
    INDEXED = "indexed"
    RECOMMENDABLE = "recommendable"
    STALE = "stale"
    REFRESHING = "refreshing"
    FAILED = "failed"


class ActivityLabel(models.TextChoices):
    RECENTLY_ACTIVE = "recently_active"
    MODERATELY_ACTIVE = "moderately_active"
    LOW_ACTIVITY = "low_activity"


class DiscoverySource(models.TextChoices):
    LANGUAGE_SEARCH = "language_search"
    TOPIC_SEARCH = "topic_search"
    SKILL_SEARCH = "skill_search"
    INTEREST_SEARCH = "interest_search"
    SIMILAR_REPO = "similar_repo"
    PREVIOUSLY_INTERACTED = "previously_interacted"


class Repository(models.Model):
    """A GitHub repository, stored once and shared by every user linked to it and by every
    developer whose candidate pool contains it (Phase 4).

    ``synced_at`` is the metadata fetch time; the other data types have their own timestamps
    (per-data-type staleness). ``is_eligible`` is null until the first completed analysis and
    is kept while the repository is STALE or REFRESHING.
    """

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

    # Phase 4: processing lifecycle and eligibility.
    lifecycle = models.CharField(
        max_length=20, choices=Lifecycle.choices, default=Lifecycle.DISCOVERED
    )
    # Time of the last lifecycle transition. Claiming for analysis is not a transition: a
    # released claim keeps the earlier state's time.
    lifecycle_changed_at = models.DateTimeField(default=timezone.now)
    lifecycle_error = models.CharField(max_length=50, blank=True)
    previous_lifecycle = models.CharField(max_length=20, choices=Lifecycle.choices, blank=True)
    stale_parts = models.JSONField(default=list, blank=True)
    is_eligible = models.BooleanField(null=True, blank=True)
    ineligible_reason = models.CharField(max_length=50, blank=True)
    # The analysis claim (FETCHING/REFRESHING): token of the analysis holding it and when that
    # analysis last renewed it. A claim not renewed for SYNC_STALE_AFTER_SECONDS is reclaimable.
    claim_token = models.UUIDField(null=True, blank=True, editable=False)
    claimed_at = models.DateTimeField(null=True, blank=True)
    # A background refresh that ended without a retry (and without FAILED): the backlog waits
    # REPO_REFRESH_RETRY_MINUTES before queueing it again. ``lifecycle_error`` holds the code.
    refresh_failed_at = models.DateTimeField(null=True, blank=True)
    # When the backlog last queued a refresh task. It is not queued again while that task can
    # still run (services/repositories/backlog.py); a completed or failed analysis clears it.
    refresh_queued_at = models.DateTimeField(null=True, blank=True)

    # Community files and labels (null = not fetched yet).
    has_contributing = models.BooleanField(null=True, blank=True)
    has_code_of_conduct = models.BooleanField(null=True, blank=True)
    has_issue_templates = models.BooleanField(null=True, blank=True)
    has_pull_request_template = models.BooleanField(null=True, blank=True)
    has_good_first_issue_label = models.BooleanField(null=True, blank=True)
    has_help_wanted_label = models.BooleanField(null=True, blank=True)

    # Setup facts from the root listing, refreshed with the dependencies (null = not fetched
    # yet; False = not found at the root, ``services/repositories/setup.py``). Never scored.
    has_ci = models.BooleanField(null=True, blank=True)
    has_tests = models.BooleanField(null=True, blank=True)
    has_dev_environment = models.BooleanField(null=True, blank=True)
    has_docker_compose = models.BooleanField(null=True, blank=True)

    # Per-data-type fetch times.
    readme_synced_at = models.DateTimeField(null=True, blank=True)
    community_synced_at = models.DateTimeField(null=True, blank=True)
    dependencies_synced_at = models.DateTimeField(null=True, blank=True)
    activity_synced_at = models.DateTimeField(null=True, blank=True)
    issues_synced_at = models.DateTimeField(null=True, blank=True)
    # The last issue fetch stopped at ISSUES_MAX_PAGES: older open issues were not stored.
    issues_truncated = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "repositories"
        indexes = [
            models.Index(fields=["-pushed_at"]),
            models.Index(fields=["lifecycle", "lifecycle_changed_at"], name="repo_lifecycle_idx"),
        ]

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


class RepositoryDependency(models.Model):
    """A dependency declared in a root-level manifest (Phase 3). Names are normalized per
    ecosystem (``services.profiling.manifests``); raw manifest contents are not stored."""

    class Ecosystem(models.TextChoices):
        PYPI = "pypi"
        NPM = "npm"
        GO = "go"
        CARGO = "cargo"
        MAVEN = "maven"
        GRADLE = "gradle"

    repository = models.ForeignKey(
        Repository, on_delete=models.CASCADE, related_name="dependencies"
    )
    ecosystem = models.CharField(max_length=20, choices=Ecosystem.choices)
    name = models.CharField(max_length=255)
    manifest_path = models.CharField(max_length=255)

    class Meta:
        ordering = ["ecosystem", "name"]
        verbose_name_plural = "repository dependencies"
        constraints = [
            models.UniqueConstraint(
                fields=["repository", "ecosystem", "name"], name="unique_repo_dependency"
            )
        ]

    def __str__(self) -> str:
        return f"{self.repository_id}:{self.ecosystem}:{self.name}"


class UserRepository(models.Model):
    """Links a user to a repository they own or contributed to (merged PRs, public pushes)."""

    class Relation(models.TextChoices):
        OWNER = "owner"
        CONTRIBUTOR = "contributor"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="repository_links"
    )
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="user_links")
    relation = models.CharField(max_length=20, choices=Relation.choices, default=Relation.OWNER)
    linked_at = models.DateTimeField(auto_now_add=True)
    # Contributor links only (null for owner links).
    merged_pr_count = models.PositiveIntegerField(null=True, blank=True)
    push_count = models.PositiveIntegerField(null=True, blank=True)
    last_contributed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "repository", "relation"], name="unique_user_repository_relation"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}->{self.repository_id} ({self.relation})"


class RepositoryReadme(models.Model):
    """Raw README of a candidate repository, stored apart from metadata and derived data.
    No row while ``Repository.readme_synced_at`` is set means the repository has no README."""

    repository = models.OneToOneField(Repository, on_delete=models.CASCADE, related_name="readme")
    content = models.TextField()
    size = models.PositiveIntegerField()
    truncated = models.BooleanField(default=False)
    fetched_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"README of {self.repository_id}"


class RepositorySnapshot(models.Model):
    """Dated activity signals of a repository (FR-REPO-004). ``None`` means unknown, never 0."""

    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="snapshots")
    captured_at = models.DateTimeField()
    stars = models.PositiveIntegerField()
    forks = models.PositiveIntegerField()
    open_issues = models.PositiveIntegerField()
    days_since_push = models.PositiveIntegerField(null=True, blank=True)
    commits_90d = models.PositiveIntegerField(null=True, blank=True)
    prs_opened_90d = models.PositiveIntegerField(null=True, blank=True)
    prs_merged_90d = models.PositiveIntegerField(null=True, blank=True)
    prs_sample_capped = models.BooleanField(default=False)
    contributors = models.PositiveIntegerField(null=True, blank=True)
    latest_release_at = models.DateTimeField(null=True, blank=True)
    activity_label = models.CharField(max_length=20, choices=ActivityLabel.choices)
    thresholds_version = models.CharField(max_length=16)

    class Meta:
        ordering = ["-captured_at"]
        # Matches repositories.queries.SNAPSHOT_NEWEST_FIRST (newest-snapshot reads).
        indexes = [models.Index(fields=["repository", "-captured_at", "-id"])]

    def __str__(self) -> str:
        return f"{self.repository_id}@{self.captured_at:%Y-%m-%d} {self.activity_label}"


class RepositoryCandidate(models.Model):
    """A repository in a developer's candidate pool (FR-REPO-002). Every way it was found is a
    ``CandidateDiscovery`` row."""

    developer = models.ForeignKey(
        "developers.DeveloperProfile", on_delete=models.CASCADE, related_name="candidates"
    )
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="candidates")
    first_discovered_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["developer", "repository"], name="unique_candidate_per_developer"
            )
        ]
        indexes = [models.Index(fields=["developer", "-last_seen_at"])]

    def __str__(self) -> str:
        return f"{self.developer_id}:{self.repository_id}"


class CandidateDiscovery(models.Model):
    candidate = models.ForeignKey(
        RepositoryCandidate, on_delete=models.CASCADE, related_name="discoveries"
    )
    source = models.CharField(max_length=30, choices=DiscoverySource.choices)
    query = models.CharField(max_length=256, blank=True)
    search_rank = models.PositiveIntegerField(null=True, blank=True)
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()

    class Meta:
        ordering = ["source", "search_rank"]
        verbose_name_plural = "candidate discoveries"
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "source", "query"], name="unique_candidate_discovery"
            )
        ]

    def __str__(self) -> str:
        return f"{self.candidate_id}:{self.source}"
