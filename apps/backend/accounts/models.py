from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Application user. GitHub identity lives on github.GitHubAccount.

    Users created through GitHub sign-in get username ``gh_<github_id>`` (stable across
    GitHub login renames) and an unusable password.
    """

    display_name = models.CharField(max_length=255, blank=True)


class AuditEvent(models.Model):
    class Action(models.TextChoices):
        SIGN_IN = "sign_in"
        SIGN_IN_FAILED = "sign_in_failed"
        LOGOUT = "logout"
        GITHUB_DISCONNECT = "github_disconnect"
        GITHUB_DATA_DELETED = "github_data_deleted"
        ACCOUNT_DELETED = "account_deleted"
        SCORING_CONFIG_ACTIVATED = "scoring_config_activated"
        GITHUB_REVOCATION_FAILED = "github_revocation_failed"

    class Outcome(models.TextChoices):
        SUCCESS = "success"
        FAILURE = "failure"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=50, choices=Action.choices)
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    metadata = models.JSONField(default=dict, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["-created_at"], name="auditevent_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action}:{self.outcome}@{self.created_at:%Y-%m-%dT%H:%M:%S}"
