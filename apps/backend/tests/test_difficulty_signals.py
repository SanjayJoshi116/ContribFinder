"""Difficulty signals are declared in the API schema (change feedback-ids-and-signal-enum,
Bug_Backlog SIM2-11, CR-9). The issue page's words for each are checked by ``tsc``
(``SIGNAL_TEXT: Record<DifficultySignal, ...>`` in ``features/issues/evidence.ts``)."""

from typing import Any

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from issues.models import DifficultySignal
from issues.serializers import DifficultyEvidenceSerializer
from services.issues import classify

from .test_issue_api import ISSUES, generated, relevant_issue  # noqa: F401 - pytest fixtures
from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    generate,
    pool,
    ready_repo,
)

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]


def evidence() -> dict[str, Any]:
    _, written = classify.difficulty(
        raw_labels=["good first issue"],
        body="Fix the typo.",
        technology_count=1,
        contribution_type="documentation",
        comments=0,
        thresholds=settings.ISSUE_DIFFICULTY,
    )
    return written


def test_classifier_writes_exactly_the_declared_signals() -> None:
    assert {signal["signal"] for signal in evidence()["signals"]} == set(DifficultySignal.values)


def test_stored_evidence_matches_the_declared_shape() -> None:
    serializer = DifficultyEvidenceSerializer(data=evidence())
    assert serializer.is_valid(), serializer.errors
    assert set(serializer.validated_data) == {"signals", "votes", "thresholds"}


def test_schema_names_the_signals(api_client: APIClient) -> None:
    response = api_client.get("/api/v1/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")
    schemas = response.json()["components"]["schemas"]
    assert schemas["DifficultySignalEnum"]["enum"] == list(DifficultySignal.values)
    analysis = schemas["IssueAnalysis"]["properties"]["difficulty_evidence"]
    assert analysis["$ref"].endswith("/DifficultyEvidence")
    assert not schemas["DifficultyEvidence"].get("required")
    vote = schemas["DifficultyVote"]["properties"]["signal"]
    assert vote["$ref"].endswith("/DifficultySignalEnum")


def test_issue_detail_returns_stored_evidence_unchanged(
    signed_in_client: APIClient,
    generated,
) -> None:
    stored = {"signals": [{"signal": "retired_signal", "vote": "beginner", "value": 1}]}
    issue = generated["django"].recommended_issues.first().issue
    type(issue).objects.filter(pk=issue.pk).update(difficulty_evidence=stored)
    body = signed_in_client.get(f"{ISSUES}/{issue.pk}").json()
    assert body["analysis"]["difficulty_evidence"] == stored
