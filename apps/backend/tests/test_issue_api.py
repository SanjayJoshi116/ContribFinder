"""Issue API: recommendation list and detail additions, issue detail, opened_issue feedback
(Phase 7, group 6)."""

from typing import Any, cast

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from developers.models import DeveloperProfile
from feedback.models import RecommendationFeedback
from github.models import GitHubAccount
from issues.models import Issue
from recommendations.models import Recommendation

from .factories import GitHubAccountFactory
from .repo_fixtures import add_candidate, make_issue
from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    generate,
    pool,
    ready_repo,
)

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]

RECS = "/api/v1/recommendations"
ISSUES = "/api/v1/issues"


def relevant_issue(repo, number: int, **fields) -> Issue:
    defaults = {
        "title": f"Support async views in Django ({number})",
        "body": "<script>alert(1)</script> Plain **text** body.",
        "raw_labels": ["good first issue", "Type: Docs"],
        "labels": ["good_first_issue", "documentation"],
        "contribution_type": "documentation",
        "contribution_type_evidence": {"by": "label", "value": "documentation"},
        "difficulty": "beginner",
        "difficulty_evidence": {"signals": [], "votes": {"beginner": 3}},
        "technologies": [
            {"slug": "django", "source": "title"},
            {"slug": "react", "source": "body"},
        ],
    }
    return cast(Issue, make_issue(repo, number, **{**defaults, **fields}))


@pytest.fixture
def generated(user, developer, pool):
    DeveloperProfile.objects.filter(pk=developer.pk).update(experience_level="beginner")
    relevant_issue(pool["django"], 1)
    relevant_issue(pool["django"], 2, difficulty="unknown", contribution_type="bug_fix")
    relevant_issue(
        pool["plain"],
        3,
        title="Speed up the parser",
        technologies=[{"slug": "python", "source": "title"}],
        labels=["help_wanted"],
        difficulty="advanced",
        contribution_type="code",
    )
    generate(user)
    return {
        name: Recommendation.objects.filter(repository=repo).first() for name, repo in pool.items()
    }


def names(body) -> list[str]:
    return [r["repository"]["full_name"] for r in body["results"]]


def walk_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in walk_keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in walk_keys(v)}
    return set()


# --- recommendation list and detail -------------------------------------------------------


def test_list_has_relevant_issue_count(signed_in_client: APIClient, generated) -> None:
    body = signed_in_client.get(RECS).json()
    counts = {r["repository"]["full_name"]: r["relevant_issue_count"] for r in body["results"]}
    assert counts == {"encode/django-tool": 2, "someone/pylib": 1}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("difficulty=beginner", ["encode/django-tool"]),
        ("difficulty=unknown", ["encode/django-tool"]),
        ("difficulty=advanced", ["someone/pylib"]),
        ("difficulty=intermediate", []),
        ("contribution_type=documentation", ["encode/django-tool"]),
        ("contribution_type=code", ["someone/pylib"]),
        ("contribution_type=bug_fix&difficulty=unknown", ["encode/django-tool"]),
        ("contribution_type=code&difficulty=beginner", []),
    ],
)
def test_issue_filters(signed_in_client: APIClient, generated, query: str, expected) -> None:
    assert names(signed_in_client.get(f"{RECS}?{query}").json()) == expected


@pytest.mark.parametrize(
    "query", ["difficulty=easy", "contribution_type=unknown", "contribution_type=docs"]
)
def test_unknown_issue_filter_values_rejected(
    signed_in_client: APIClient, generated, query: str
) -> None:
    response = signed_in_client.get(f"{RECS}?{query}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_detail_lists_relevant_issues_in_order(signed_in_client: APIClient, generated) -> None:
    body = signed_in_client.get(f"{RECS}/{generated['django'].pk}").json()
    assert [i["number"] for i in body["issues"]] == [1, 2]
    first = body["issues"][0]
    assert set(first) == {
        "id",
        "number",
        "title",
        "url",
        "labels",
        "contribution_type",
        "difficulty",
        "reasons",
    }
    assert first["labels"] == ["good_first_issue", "documentation"]
    assert first["url"].endswith("/issues/1")
    assert first["reasons"][0].keys() == {"type", "text", "detail"}
    assert body["issues"][1]["difficulty"] == "unknown"
    assert not {"score", "rank"} & walk_keys(body["issues"])


def test_detail_without_relevant_issues(signed_in_client: APIClient, user, developer) -> None:
    add_candidate(developer, ready_repo(1, "a/one", topics=("django",)))
    generate(user)
    rec = Recommendation.objects.get()
    body = signed_in_client.get(f"{RECS}/{rec.pk}").json()
    assert body["issues"] == [] and body["relevant_issue_count"] == 0


def test_list_query_count_constant_with_issues(
    signed_in_client: APIClient,
    user,
    developer,
) -> None:
    def count() -> int:
        with CaptureQueriesContext(connection) as ctx:
            assert signed_in_client.get(RECS).status_code == 200
        return len(ctx)

    first = ready_repo(1, "a/one", topics=("django",))
    add_candidate(developer, first)
    relevant_issue(first, 1)
    generate(user)
    few = count()
    for i in range(2, 10):
        repo = ready_repo(i, f"a/r{i}", topics=("django", "cli"))
        add_candidate(developer, repo)
        relevant_issue(repo, 1)
        relevant_issue(repo, 2)
    generate(user)
    assert Recommendation.objects.filter(relevant_issue_count__gt=0).count() > 1
    assert count() == few


# --- issue detail -------------------------------------------------------------------------


def test_issue_detail_separates_github_and_analysis(signed_in_client: APIClient, generated) -> None:
    issue = Issue.objects.get(number=1)
    response = signed_in_client.get(f"{ISSUES}/{issue.pk}")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "github", "analysis"}
    github, analysis = body["github"], body["analysis"]
    assert github["repository_full_name"] == "encode/django-tool"
    assert github["labels"] == ["good first issue", "Type: Docs"]  # raw, as GitHub sent them
    assert github["body"] == "<script>alert(1)</script> Plain **text** body."  # plain text
    assert set(github) == {
        "repository_full_name",
        "number",
        "title",
        "body",
        "labels",
        "state",
        "comments",
        "created_at",
        "updated_at",
        "url",
    }
    assert analysis["labels"] == ["good_first_issue", "documentation"]
    assert analysis["contribution_type"] == "documentation"
    assert analysis["contribution_type_evidence"] == {"by": "label", "value": "documentation"}
    assert analysis["difficulty"] == "beginner"
    assert analysis["technologies"] == [
        {"slug": "django", "name": "Django", "source": "title", "matched": True},
        {"slug": "react", "name": "React", "source": "body", "matched": False},
    ]
    assert analysis["reasons"] and all("%" not in r["text"] for r in analysis["reasons"])
    assert analysis["recommendation"] == {
        "id": generated["django"].pk,
        "repository_full_name": "encode/django-tool",
        "match_label": generated["django"].match_label,
    }
    assert not {"score", "rank", "signal_scores"} & walk_keys(body)


def test_issue_not_relevant_to_the_user_is_404(signed_in_client: APIClient, generated) -> None:
    stray = make_issue(generated["django"].repository, 50, has_assignee=True)
    assert signed_in_client.get(f"{ISSUES}/{stray.pk}").status_code == 404
    assert signed_in_client.get(f"{ISSUES}/999999").status_code == 404


def test_another_users_issue_is_404(generated, api_client: APIClient) -> None:
    other = cast(GitHubAccount, GitHubAccountFactory()).user
    DeveloperProfile.objects.create(user=other, analyzed_at=timezone.now())
    api_client.force_login(other)
    issue = Issue.objects.get(number=1)
    response = api_client.get(f"{ISSUES}/{issue.pk}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_issue_detail_signed_out(api_client: APIClient) -> None:
    assert api_client.get(f"{ISSUES}/1").status_code == 401


# --- opened_issue feedback ----------------------------------------------------------------


def post(client: APIClient, rec: Recommendation, payload: dict[str, Any]):
    return client.post(f"{RECS}/{rec.pk}/feedback", payload, format="json")


def test_opened_issue_recorded_with_snapshot(signed_in_client: APIClient, user, generated) -> None:
    rec = generated["django"]
    issue = Issue.objects.get(number=2)
    response = post(signed_in_client, rec, {"action": "opened_issue", "issue_id": issue.pk})
    assert response.status_code == 204
    event = RecommendationFeedback.objects.get(user=user, action="opened_issue")
    assert (event.issue_id, event.issue_number, event.recommendation_id) == (issue.pk, 2, rec.pk)

    issue.delete()  # closed and removed by a later refresh
    event.refresh_from_db()
    assert event.issue is None and event.issue_number == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "opened_issue"},
        {"action": "opened_issue", "issue_id": None},
        {"action": "opened_repository", "issue_id": 1},
    ],
    ids=["missing", "null", "wrong-action"],
)
def test_issue_id_validation(signed_in_client: APIClient, user, generated, payload) -> None:
    response = post(signed_in_client, generated["django"], payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert not RecommendationFeedback.objects.exists()


def test_issue_of_another_recommendation_rejected(signed_in_client: APIClient, generated) -> None:
    other_issue = Issue.objects.get(number=3)  # relevant to someone/pylib, not django-tool
    response = post(
        signed_in_client,
        generated["django"],
        {"action": "opened_issue", "issue_id": other_issue.pk},
    )
    assert response.status_code == 400
    assert "issue_id" in response.json()["error"]["details"]
    assert not RecommendationFeedback.objects.exists()
