"""Review sweep of `feedback/` (Bug_Backlog.md batch 42): FB-1 (opened_issue relevance checked
under the recommendation lock) and FB-5 (light ownership check in the views)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from feedback import api as feedback_api
from feedback.models import RecommendationFeedback
from issues.models import Issue, RecommendedIssue
from recommendations.models import Recommendation
from repositories.models import Repository

from .test_issue_api import generated, post  # noqa: F401 - pytest fixtures
from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    pool,
    ready_repo,
)

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]

RECS = "/api/v1/recommendations"
REC_TABLE = '"recommendations_recommendation"'


def opened(client: APIClient, rec: Recommendation, issue: Issue):
    return post(client, rec, {"action": "opened_issue", "issue_id": issue.pk})


# --- FB-1 ---------------------------------------------------------------------------------


def test_relevant_issue_is_recorded(signed_in_client: APIClient, generated) -> None:
    response = opened(signed_in_client, generated["django"], Issue.objects.get(number=1))
    assert response.status_code == 204
    assert RecommendationFeedback.objects.filter(action="opened_issue").count() == 1


def test_issue_dropped_after_the_ownership_check_stores_nothing(
    signed_in_client: APIClient, generated, monkeypatch
) -> None:
    """A generation that commits between the view's check and the lock drops the issue from
    the recommendation's relevant issues: the check under the lock sees the new set, and the
    race is answered like a recommendation gone meanwhile (no event, no error)."""
    rec = generated["django"]
    issue = Issue.objects.get(number=1)
    own = feedback_api._own_repository_id

    def regenerated_meanwhile(request, pk):
        found = own(request, pk)
        RecommendedIssue.objects.filter(recommendation=rec, issue=issue).delete()
        return found

    monkeypatch.setattr(feedback_api, "_own_repository_id", regenerated_meanwhile)
    response = opened(signed_in_client, rec, issue)
    assert response.status_code == 204
    assert not RecommendationFeedback.objects.exists()


def test_issue_closed_meanwhile_stores_nothing(signed_in_client: APIClient, generated) -> None:
    issue = Issue.objects.get(number=1)
    issue_pk = issue.pk
    issue.delete()  # an issue refresh closed it after the page loaded
    response = post(
        signed_in_client, generated["django"], {"action": "opened_issue", "issue_id": issue_pk}
    )
    assert response.status_code == 204
    assert not RecommendationFeedback.objects.exists()


def test_issue_of_another_repository_is_rejected(signed_in_client: APIClient, generated) -> None:
    other = Issue.objects.get(number=3)  # someone/pylib's issue, never django-tool's
    response = opened(signed_in_client, generated["django"], other)
    assert response.status_code == 400
    assert "issue_id" in response.json()["error"]["details"]
    assert not RecommendationFeedback.objects.exists()


def test_dismiss_of_a_repository_deleted_meanwhile_is_404(
    signed_in_client: APIClient, generated, monkeypatch
) -> None:
    rec = generated["django"]
    own = feedback_api._own_repository_id

    def deleted_meanwhile(request, pk):
        found = own(request, pk)
        Repository.objects.filter(pk=rec.repository_id).delete()  # delete-data, cascading
        return found

    monkeypatch.setattr(feedback_api, "_own_repository_id", deleted_meanwhile)
    response = signed_in_client.post(f"{RECS}/{rec.pk}/dismiss", {}, format="json")
    assert response.status_code == 404
    assert not RecommendationFeedback.objects.exists()


def test_recommendation_gone_before_the_lock_stores_nothing(
    signed_in_client: APIClient, generated, monkeypatch
) -> None:
    rec = generated["django"]
    own = feedback_api._own_repository_id

    def dismissed_meanwhile(request, pk):
        found = own(request, pk)
        Recommendation.objects.filter(pk=rec.pk).delete()
        return found

    monkeypatch.setattr(feedback_api, "_own_repository_id", dismissed_meanwhile)
    response = opened(signed_in_client, rec, Issue.objects.get(number=1))
    assert response.status_code == 204
    assert not RecommendationFeedback.objects.exists()


# --- FB-5 ---------------------------------------------------------------------------------


def recommendation_reads(queries) -> list[str]:
    return [
        q["sql"]
        for q in queries
        if q["sql"].startswith("SELECT") and f"FROM {REC_TABLE}" in q["sql"]
    ]


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("post", "feedback", {"action": "viewed"}),
        ("post", "save", None),
        ("delete", "save", None),
        ("post", "dismiss", None),
    ],
    ids=["viewed", "save", "unsave", "dismiss"],
)
def test_ownership_check_reads_only_the_recommendation(
    signed_in_client: APIClient, generated, method, suffix, body
) -> None:
    rec = generated["django"]
    with CaptureQueriesContext(connection) as ctx:
        response = getattr(signed_in_client, method)(
            f"{RECS}/{rec.pk}/{suffix}", body, format="json"
        )
    assert response.status_code in (200, 204)
    reads = recommendation_reads(ctx.captured_queries)
    # The ownership check loads no repository or configuration; the service's re-read is the
    # only full read.
    assert '"repositories_repository"' not in reads[0]
    assert '"recommendations_scoringconfig"' not in reads[0]
    assert len(reads) <= 2
