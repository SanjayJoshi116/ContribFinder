from typing import cast

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from github.models import GitHubAccount
from services.profiling.analysis import ProfileAnalysisService

from .factories import GitHubAccountFactory
from .profile_data import add_repo

pytestmark = pytest.mark.django_db


@pytest.fixture
def analyzed(synced):
    ProfileAnalysisService(synced).run()
    return synced


def test_profile(analyzed, signed_in_client: APIClient) -> None:
    response = signed_in_client.get("/api/v1/profile")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "summary",
        "languages",
        "preferred_project_size",
        "preferred_issue_difficulty",
        "analyzed_at",
        "skill_count",
        "interest_count",
    }
    assert body["languages"][0] == {"name": "Python", "bytes": 2000, "share": 1.0, "repo_count": 2}
    assert body["skill_count"] >= 5
    assert "experience" not in response.content.decode()


def test_profile_not_analyzed(signed_in_client: APIClient) -> None:
    response = signed_in_client.get("/api/v1/profile")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_analyzed"


def test_skills_with_evidence(analyzed, signed_in_client: APIClient) -> None:
    body = signed_in_client.get("/api/v1/profile/skills").json()
    results = body["results"]
    confidences = [s["confidence"] for s in results]
    assert confidences == sorted(confidences, reverse=True)
    python = next(s for s in results if s["skill"]["slug"] == "python")
    assert python["skill"] == {"slug": "python", "name": "Python", "category": "language"}
    assert python["evidence_summary"]["by_source"] == {"readme": 1, "language": 2}
    assert python["evidence_summary"]["repository_count"] == 2
    assert python["evidence_summary"]["last_observed_at"] is not None
    language = next(e for e in python["evidence"] if e["source"] == "language")
    assert language["repository"]["full_name"].startswith("octocat/")
    assert language["repository"]["html_url"].startswith("https://github.com/")
    readme = next(e for e in python["evidence"] if e["source"] == "readme")
    assert readme["repository"] is None


def test_skills_category_filter(analyzed, signed_in_client: APIClient) -> None:
    results = signed_in_client.get("/api/v1/profile/skills?category=framework").json()["results"]
    assert results
    assert {s["skill"]["category"] for s in results} == {"framework"}
    assert signed_in_client.get("/api/v1/profile/skills?category=nope").status_code == 400


def test_interests(analyzed, signed_in_client: APIClient) -> None:
    results = signed_in_client.get("/api/v1/profile/interests").json()["results"]
    slugs = [i["interest"]["slug"] for i in results]
    assert "developer-tooling" in slugs
    tooling = results[slugs.index("developer-tooling")]
    assert {e["source"] for e in tooling["evidence"]} >= {"topic"}


def test_isolation(analyzed, api_client: APIClient) -> None:
    other = cast(GitHubAccount, GitHubAccountFactory()).user
    api_client.force_login(other)
    assert api_client.get("/api/v1/profile/skills").json()["results"] == []
    assert api_client.get("/api/v1/profile/interests").json()["results"] == []
    assert api_client.get("/api/v1/profile").status_code == 404


@pytest.mark.parametrize(
    "url", ["/api/v1/profile", "/api/v1/profile/skills", "/api/v1/profile/interests"]
)
def test_signed_out(api_client: APIClient, url: str) -> None:
    assert api_client.get(url).status_code == 401


def test_query_count_is_constant(analyzed, signed_in_client: APIClient) -> None:
    with CaptureQueriesContext(connection) as small:
        signed_in_client.get("/api/v1/profile/skills")
    for n in range(10, 20):
        add_repo(analyzed, n, languages={"Rust": 100}, topics=(f"t{n}", "graphql", "redis"))
    ProfileAnalysisService(analyzed).run()
    with CaptureQueriesContext(connection) as large:
        signed_in_client.get("/api/v1/profile/skills")
    assert len(large) == len(small)
