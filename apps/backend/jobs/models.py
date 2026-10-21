from django.conf import settings
from django.db import models
from django.db.models import Q


class SyncJob(models.Model):
    """A tracked background job (SRS-2 §46). Generic: later phases add job types.

    ``steps`` maps step name → StepState. ``error_code`` is machine-readable and safe to expose;
    ``error_detail`` and ``metadata`` are internal and never contain credentials.
    """

    class JobType(models.TextChoices):
        GITHUB_PROFILE_SYNC = "github_profile_sync"
        PROFILE_ANALYSIS = "profile_analysis"
        REPOSITORY_DISCOVERY = "repository_discovery"
        RECOMMENDATION_GENERATION = "recommendation_generation"

    class Status(models.TextChoices):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        RETRYING = "RETRYING"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"
        CANCELLED = "CANCELLED"

    class StepState(models.TextChoices):
        PENDING = "pending"
        RUNNING = "running"
        DONE = "done"
        NOT_FOUND = "not_found"
        SKIPPED = "skipped"
        FAILED = "failed"

    ACTIVE_STATUSES = (Status.PENDING, Status.RUNNING, Status.RETRYING)
    TERMINAL_STATUSES = (Status.COMPLETED, Status.FAILED, Status.CANCELLED)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sync_jobs"
    )
    job_type = models.CharField(max_length=50, choices=JobType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    steps = models.JSONField(default=dict, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=50, blank=True)
    error_detail = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Set by each claim; only the worker holding the current token may write (job-claim-fencing
    # D1). Internal: never serialized.
    claim_token = models.UUIDField(null=True, blank=True, editable=False)
    # Generation jobs: a generation was requested while this one was RUNNING, so it runs again
    # once it completes (recommendation-consistency D6). A column, not metadata: the job
    # rewrites its metadata wholesale. Internal: never serialized.
    rerun_requested = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "job_type", "-created_at"])]
        constraints = [
            # At most one active job per user and type, enforced by the database.
            models.UniqueConstraint(
                fields=["user", "job_type"],
                condition=Q(status__in=["PENDING", "RUNNING", "RETRYING"]),
                name="one_active_job_per_user_and_type",
            )
        ]

    def __str__(self) -> str:
        return f"SyncJob({self.job_type}, {self.status}, user={self.user_id})"

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES
