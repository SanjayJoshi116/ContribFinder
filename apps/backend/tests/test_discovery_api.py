"""Discovery status and candidate list endpoints (Phase 4, group 8)."""

from datetime import timedelta
from typing import cast

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from developers.models import DeveloperProfile
from e2e.builders import add_candidate, make_candidate_repo
from github.models import GitHubAccount
from jobs.models import SyncJob
from repositories.models import RepositorySnapshot

from .factories import GitHubAccountFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def profile(user) -> DeveloperProfile:
    return DeveloperProfile.objects.create(user=user, analyzed_at=timezone.now())


def snapshot(repo, label: str) -> None:
    RepositorySnapshot.objects.create(
        repository=repo,
        captured_at=timezone.now(),
        stars=1,
        forks=0,
        open_issues=0,
        activity_label=label,
        thresholds_version="x",
    )


@pytest.fixture
def pool(profile):
    now = timezone.now()
    eligible = make_candidate_repo(1, "encode/httpx", lifecycle="recommendable", is_eligible=True)
    snapshot(eligible, "low_activity")
    snapshot(eligible, "recently_active")  # the latest one counts
    ineligible = make_candidate_repo(
        2, "old/lib", lifecycle="indexed", is_eligible=False, ineligible_reason="archived"
    )
    pending = make_candidate_repo(3, "new/thing")
    add_candidate(profile, eligible, seen=now - timedelta(hours=1))
    add_candidate(profile, eligible, source="interest_search", query="topic:cli", rank=4)
    add_candidate(profile, ineligible, seen=now - timedelta(days=1))
    add_candidate(profile, pending, source="previously_interacted", query="", rank=None, seen=now)
    return {"eligible": eligible, "ineligible": ineligible, "pending": pending}


def test_status_never_discovered(signed_in_client: APIClient) -> None:
    body = signed_in_client.get("/api/v1/discovery/status").json()
    assert body == {
        "job": None,
        "last_completed_at": None,
        "pool": {
            "total": 0,
            "eligible": 0,
            "awaiting_analysis": 0,
            "ineligible": 0,
            "by_source": {},
        },
    }


def test_status_with_job_and_counts(user, pool, signed_in_client: APIClient) -> None:
    done_at = timezone.now()
    SyncJob.objects.create(
        user=user,
        job_type="repository_discovery",
        status="COMPLETED",
        completed_at=done_at,
        steps={"queries": "done"},
    )
    body = signed_in_client.get("/api/v1/discovery/status").json()
    assert body["job"]["status"] == "COMPLETED"
    assert list(body["job"]["steps"]) == ["queries", "search", "interactions", "pool", "analysis"]
    assert body["last_completed_at"] is not None
    assert body["pool"] == {
        "total": 3,
        "eligible": 1,
        "awaiting_analysis": 1,
        "ineligible": 1,
        "by_source": {"language_search": 2, "interest_search": 1, "previously_interacted": 1},
    }


def test_candidate_shape(pool, signed_in_client: APIClient) -> None:
    body = signed_in_client.get("/api/v1/discovery/candidates").json()
    assert body["count"] == 3
    names = [c["repository"]["full_name"] for c in body["results"]]
    assert names == ["encode/httpx", "new/thing", "old/lib"]  # eligible, awaiting, ineligible
    httpx = body["results"][0]
    assert set(httpx) == {
        "id",
        "repository",
        "lifecycle",
        "eligible",
        "ineligible_reason",
        "activity_label",
        "discoveries",
        "first_discovered_at",
        "last_seen_at",
    }
    assert httpx["repository"]["owner"] == "encode"
    assert httpx["repository"]["license"] == "MIT"
    assert (httpx["lifecycle"], httpx["eligible"], httpx["activity_label"]) == (
        "recommendable",
        True,
        "recently_active",
    )
    assert {d["source"] for d in httpx["discoveries"]} == {"language_search", "interest_search"}
    assert not {"score", "rank", "match"} & set(httpx)
    assert body["results"][1]["eligible"] is None  # awaiting analysis


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("source=previously_interacted", ["new/thing"]),
        ("source=interest_search", ["encode/httpx"]),
        ("eligible=true", ["encode/httpx"]),
        ("eligible=false", ["old/lib"]),
        ("activity=recently_active", ["encode/httpx"]),
    ],
)
def test_filters(pool, signed_in_client: APIClient, query: str, expected) -> None:
    body = signed_in_client.get(f"/api/v1/discovery/candidates?{query}").json()
    assert [c["repository"]["full_name"] for c in body["results"]] == expected


def test_order_within_state(profile, signed_in_client: APIClient) -> None:
    add_candidate(profile, make_candidate_repo(1, "a/rank9"), rank=9)
    two = make_candidate_repo(2, "b/rank2")
    add_candidate(profile, two, rank=9)
    add_candidate(profile, two, query="topic:cli", rank=2)
    add_candidate(profile, make_candidate_repo(3, "c/unranked"), query="", rank=None)
    add_candidate(
        profile,
        make_candidate_repo(4, "d/mine"),
        source="previously_interacted",
        query="",
        rank=None,
    )
    body = signed_in_client.get("/api/v1/discovery/candidates").json()
    names = [c["repository"]["full_name"] for c in body["results"]]
    assert names == ["d/mine", "b/rank2", "a/rank9", "c/unranked"]


def test_equal_rank_most_recently_found_first(profile, signed_in_client: APIClient) -> None:
    """The pool order: the cap keeps the more recently found candidate first, so does the list."""
    now = timezone.now()
    add_candidate(profile, make_candidate_repo(1, "a/older"), rank=3, seen=now - timedelta(days=2))
    add_candidate(profile, make_candidate_repo(2, "b/newer"), rank=3, seen=now)
    body = signed_in_client.get("/api/v1/discovery/candidates").json()
    assert [c["repository"]["full_name"] for c in body["results"]] == ["b/newer", "a/older"]


def test_other_users_candidates_invisible(pool, api_client: APIClient) -> None:
    other = cast(GitHubAccount, GitHubAccountFactory()).user
    DeveloperProfile.objects.create(user=other, analyzed_at=timezone.now())
    api_client.force_login(other)
    assert api_client.get("/api/v1/discovery/candidates").json()["count"] == 0
    assert api_client.get("/api/v1/discovery/status").json()["pool"]["total"] == 0


@pytest.mark.parametrize("path", ["/api/v1/discovery/status", "/api/v1/discovery/candidates"])
def test_signed_out(api_client: APIClient, path: str) -> None:
    assert api_client.get(path).status_code == 401


@pytest.mark.respx(assert_all_called=False)
def test_no_github_requests(pool, signed_in_client: APIClient, respx_mock) -> None:
    signed_in_client.get("/api/v1/discovery/status")
    signed_in_client.get("/api/v1/discovery/candidates")
    assert not respx_mock.calls


def test_query_count_constant(profile, signed_in_client: APIClient) -> None:
    def count() -> int:
        with CaptureQueriesContext(connection) as ctx:
            assert signed_in_client.get("/api/v1/discovery/candidates").status_code == 200
        return len(ctx)

    add_candidate(profile, make_candidate_repo(1))
    few = count()
    for n in range(2, 12):
        repo = make_candidate_repo(n)
        snapshot(repo, "low_activity")
        add_candidate(profile, repo)
    assert count() == few
