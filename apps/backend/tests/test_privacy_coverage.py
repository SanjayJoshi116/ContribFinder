"""Every model holding a user's data is deleted or deliberately kept, and the privacy page names
it (change dev-scripts-checks, H-19). A new user-linked model fails here until it is classified.
"""

from pathlib import Path
from typing import Any

from django.apps import apps
from django.db import models

from accounts.models import User

PRIVACY_PAGE = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "routes" / "PrivacyPage.tsx"
)

# Deleted explicitly by services.data_deletion.delete_github_data.
DELETED = {
    "developers.DeveloperProfile": "Derived developer profile",
    "github.GitHubProfile": "Public profile information",
    "repositories.UserRepository": "Public repository metadata and README content",
    "feedback.SavedRepository": "Saved and hidden projects",
    "feedback.DismissedRepository": "Saved and hidden projects",
    "feedback.RecommendationFeedback": "Feedback events",
    "jobs.SyncJob": "Sync and job history",
}
# Kept by delete-data; removed (or unlinked) only with the account.
KEPT = {
    "accounts.User": "GitHub account ID",
    "github.GitHubAccount": "GitHub access credential (encrypted)",
    "accounts.AuditEvent": "Audit entries",
    "admin.LogEntry": None,  # Django admin history of staff accounts, not user data
}


def _links(model: type[models.Model]) -> list[models.ForeignKey[Any, Any]]:
    """Concrete foreign keys and one-to-one fields (``OneToOneField`` is a ``ForeignKey``)."""
    return [f for f in model._meta.get_fields() if isinstance(f, models.ForeignKey)]


def _user_linked() -> set[type[models.Model]]:
    linked: set[type[models.Model]] = {User}
    changed = True
    while changed:
        changed = False
        for model in apps.get_models():
            if model not in linked and any(f.related_model in linked for f in _links(model)):
                linked.add(model)
                changed = True
    return linked


def _covered(model: type[models.Model], deleted: set[type[models.Model]]) -> bool:
    """Deleted itself, or removed by a database cascade from a deleted model."""
    return model in deleted or any(
        f.related_model in deleted and f.remote_field.on_delete is models.CASCADE
        for f in _links(model)
    )


def test_every_user_linked_model_is_deleted_or_kept() -> None:
    deleted = {apps.get_model(label) for label in DELETED}
    kept = {apps.get_model(label) for label in KEPT}
    linked = _user_linked()
    # Cascades reach further than one hop (profile → skill → evidence).
    changed = True
    while changed:
        changed = False
        for model in linked - deleted - kept:
            if _covered(model, deleted):
                deleted.add(model)
                changed = True

    unclassified = sorted(m._meta.label for m in linked - deleted - kept)
    assert unclassified == [], (
        "Add these models to DELETED (and to services.data_deletion) or to KEPT, and to the "
        f"privacy page: {unclassified}"
    )


def test_privacy_page_names_every_category() -> None:
    page = PRIVACY_PAGE.read_text(encoding="utf-8")
    categories = {c for c in [*DELETED.values(), *KEPT.values()] if c}
    missing = sorted(c for c in categories if f"name: '{c}'" not in page)
    assert missing == []
