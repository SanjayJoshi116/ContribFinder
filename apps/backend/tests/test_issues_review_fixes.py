"""Review sweep of ``issues/`` (Bug_Backlog.md batch 40, ISS-1…ISS-8)."""

import pytest
from django.test import Client
from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from developers.models import DeveloperProfile
from e2e.builders import make_candidate_repo, make_issue
from issues.models import Issue, RecommendedIssue
from issues.serializers import IssueTechnologySerializer
from services.issues import technologies

from .shared_fixtures import assert_changelist_flat, assert_view_only
from .test_models_phase5 import make_recommendation

pytestmark = pytest.mark.django_db


def recommended_issue(n: int) -> RecommendedIssue:
    """One developer, recommendation, repository and issue per ``n``."""
    user = User.objects.create(username=f"dev{n}")
    profile = DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())
    repo = make_candidate_repo(1000 + n)
    recommendation = make_recommendation(profile, repo)
    return RecommendedIssue.objects.create(
        recommendation=recommendation, issue=make_issue(repo, 1), rank=1, score=0.5
    )


# --- View-only admin (ISS-1, ISS-2, ISS-8) -------------------------------------------------


@pytest.mark.parametrize("model", [Issue, RecommendedIssue], ids=lambda m: m.__name__)
def test_staff_cannot_add_change_or_delete_issue_data(admin_user: User, model) -> None:
    assert_view_only(model, admin_user)


def test_deleting_an_issue_through_the_admin_is_refused(admin_client: Client) -> None:
    link = recommended_issue(1)
    delete = admin_client.post(f"/admin/issues/issue/{link.issue_id}/delete/", {"post": "yes"})
    assert delete.status_code == 403
    response = admin_client.post(
        "/admin/issues/issue/",
        {"action": "delete_selected", "_selected_action": [link.issue_id], "post": "yes"},
    )
    assert response.status_code in {200, 302}
    assert RecommendedIssue.objects.filter(pk=link.pk).exists()


# --- Changelist queries (ISS-5) --------------------------------------------------------------


@pytest.mark.parametrize("path", ["issue", "recommendedissue"])
def test_changelist_query_count_does_not_grow_with_rows(admin_client: Client, path: str) -> None:
    assert_changelist_flat(admin_client, f"/admin/issues/{path}/", recommended_issue)


# --- Technology sources (ISS-7) --------------------------------------------------------------


def test_technology_source_choices_come_from_the_detector() -> None:
    field = IssueTechnologySerializer().fields["source"]
    assert isinstance(field, serializers.ChoiceField)
    assert list(field.choices) == [technologies.TITLE, technologies.LABEL, technologies.BODY]
