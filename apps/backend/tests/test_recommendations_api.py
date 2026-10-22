"""Recommendation list, detail and status endpoints (Phase 5, group 6)."""

from typing import cast

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from developers.models import DeveloperProfile
from github.models import GitHubAccount
from jobs.models import SyncJob
from recommendations.models import Recommendation
from repositories.models import RepositoryReadme

from .factories import GitHubAccountFactory
from .repo_fixtures import add_candidate
from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    generate,
    pool,
    ready_repo,
)

pytestmark = [pytest.mark.django_db, pytest.mark.respx(assert_all_called=False)]

LIST = "/api/v1/recommendations"


@pytest.fixture
def generated(user, developer, pool):
    generate(user)
    return {
        name: Recommendation.objects.filter(repository=repo).first() for name, repo in pool.items()
    }


def names(body) -> list[str]:
    return [r["repository"]["full_name"] for r in body["results"]]


def test_list_shape_without_score(signed_in_client: APIClient, generated) -> None:
    body = signed_in_client.get(LIST).json()
    assert body["count"] == Recommendation.objects.count()
    first = body["results"][0]
    assert first["repository"]["full_name"] == "encode/django-tool"
    assert set(first) == {
        "id",
        "repository_id",
        "repository",
        "match_label",
        "technologies",
        "reasons",
        "activity_label",
        "size",
        "openness",
        "saved",
        "relevant_issue_count",
        "generated_at",
    }
    assert not {"score", "rank", "signal_scores"} & set(first)
    assert first["match_label"] == "strong"
    assert first["reasons"][0].keys() == {"type", "text", "detail"}
    assert first["openness"]["contributing"] is True
    django = next(t for t in first["technologies"] if t["slug"] == "django")
    assert django["matched"] is True


def test_rank_order(signed_in_client: APIClient, generated) -> None:
    body = signed_in_client.get(LIST).json()
    ranks = [Recommendation.objects.get(pk=r["id"]).rank for r in body["results"]]
    assert ranks == sorted(ranks)


def test_irrelevant_candidate_is_not_recommended(generated) -> None:
    assert generated["go"] is None  # active, but nothing in it matches the developer


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ["encode/django-tool", "someone/pylib"]),
        ("language=Python", ["encode/django-tool", "someone/pylib"]),
        ("language=go", []),
        ("framework=django", ["encode/django-tool"]),
        ("activity=low_activity", ["someone/pylib"]),
        ("match=strong", ["encode/django-tool"]),
        ("match=good", ["someone/pylib"]),
        ("size=medium&language=python&activity=recently_active", ["encode/django-tool"]),
    ],
)
def test_filters(signed_in_client: APIClient, generated, query: str, expected) -> None:
    assert names(signed_in_client.get(f"{LIST}?{query}").json()) == expected


@pytest.mark.parametrize("query", ["activity=healthy", "match=87", "framework=nope", "size=huge"])
def test_invalid_filter_value(signed_in_client: APIClient, generated, query: str) -> None:
    response = signed_in_client.get(f"{LIST}?{query}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_detail(signed_in_client: APIClient, generated) -> None:
    rec = generated["django"]
    RepositoryReadme.objects.create(
        repository=rec.repository,
        content="# Django tool\n\nA **fast** tool. See [docs](https://x.example).",
        size=60,
        fetched_at=timezone.now(),
    )
    body = signed_in_client.get(f"{LIST}/{rec.pk}").json()
    assert body["readme_excerpt"] == "Django tool A fast tool. See docs ."
    assert body["languages"] == [{"language": "Python", "share": 1.0}]
    assert body["activity_signals"]["contributors"] == 25
    assert "score" not in body


def test_detail_without_readme(signed_in_client: APIClient, generated) -> None:
    body = signed_in_client.get(f"{LIST}/{generated['plain'].pk}").json()
    assert body["readme_excerpt"] == ""


def test_other_users_recommendations_are_invisible(generated, api_client: APIClient) -> None:
    other = cast(GitHubAccount, GitHubAccountFactory()).user
    DeveloperProfile.objects.create(user=other, analyzed_at=timezone.now())
    api_client.force_login(other)
    assert api_client.get(LIST).json()["count"] == 0
    assert api_client.get(f"{LIST}/{generated['django'].pk}").status_code == 404


def test_status(signed_in_client: APIClient, user, developer) -> None:
    assert signed_in_client.get(f"{LIST}/status").json() == {
        "job": None,
        "last_generated_at": None,
        "count": 0,
        "config_version": None,
    }


def test_status_after_generation(signed_in_client: APIClient, generated) -> None:
    body = signed_in_client.get(f"{LIST}/status").json()
    assert body["job"]["job_type"] == "recommendation_generation"
    assert body["job"]["status"] == "COMPLETED"
    assert body["count"] == Recommendation.objects.count()
    assert body["config_version"] == "v2-deterministic"
    assert body["last_generated_at"] is not None


@pytest.mark.parametrize("path", [LIST, f"{LIST}/status", f"{LIST}/1"])
def test_signed_out(api_client: APIClient, path: str) -> None:
    assert api_client.get(path).status_code == 401


def test_query_count_constant(signed_in_client: APIClient, user, developer) -> None:
    def count() -> int:
        with CaptureQueriesContext(connection) as ctx:
            assert signed_in_client.get(LIST).status_code == 200
        return len(ctx)

    add_candidate(developer, ready_repo(1, "a/one", topics=("django",)))
    generate(user)
    few = count()
    for i in range(2, 10):
        add_candidate(developer, ready_repo(i, f"a/r{i}", topics=("django", "cli")))
    generate(user)
    assert Recommendation.objects.count() > 1
    assert count() == few


def test_no_github_requests(signed_in_client: APIClient, generated, respx_mock) -> None:
    signed_in_client.get(LIST)
    signed_in_client.get(f"{LIST}/status")
    signed_in_client.get(f"{LIST}/{generated['django'].pk}")
    assert not respx_mock.calls
    assert SyncJob.objects.filter(job_type="recommendation_generation").count() == 1
