"""Recorded GitHub responses for one candidate repository, and pool helpers (Phase 4)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import respx
from django.utils import timezone

from developers.models import DeveloperProfile
from repositories.models import CandidateDiscovery, Repository, RepositoryCandidate

API = "https://api.github.com"


def repo_payload(full_name: str, github_id: int, **extra: Any) -> dict[str, Any]:
    owner, name = full_name.split("/")
    return {
        "id": github_id,
        "name": name,
        "full_name": full_name,
        "owner": {"login": owner},
        "html_url": f"https://github.com/{full_name}",
        "description": f"{name} project",
        "default_branch": "main",
        "stargazers_count": 500,
        "forks_count": 40,
        "open_issues_count": 12,
        "language": "Python",
        "fork": False,
        "archived": False,
        "topics": ["python", "http"],
        "license": {"spdx_id": "MIT"},
        "pushed_at": (timezone.now() - timedelta(days=3)).isoformat(),
        **extra,
    }


def mock_repo_api(
    router: respx.MockRouter,
    full_name: str,
    github_id: int,
    *,
    readme: str | None = "# Project\nA library.",
    community: dict[str, Any] | None = None,
    labels: tuple[str, ...] = ("good first issue", "Help Wanted"),
    manifests: dict[str, str] | None = None,
    commits: int = 42,
    issues: list[dict[str, Any]] | None = None,
    **payload: Any,
) -> dict[str, respx.Route]:
    base = f"{API}/repos/{full_name}"
    now = timezone.now()
    manifests = {"pyproject.toml": '[project]\ndependencies = ["httpx", "django"]\n'} | (
        manifests or {}
    )
    routes = {
        "metadata": router.get(base).respond(
            200, json=repo_payload(full_name, github_id, **payload)
        ),
        "languages": router.get(f"{base}/languages").respond(200, json={"Python": 9000}),
        "readme": router.get(f"{base}/readme").respond(
            *((200,) if readme is not None else (404,)),
            **({"text": readme} if readme is not None else {"json": {"message": "Not Found"}}),
        ),
        "community": router.get(f"{base}/community/profile").respond(
            200,
            json={
                "files": community
                if community is not None
                else {
                    "contributing": {"url": "c"},
                    "code_of_conduct_file": {"url": "coc"},
                    "issue_template": {"url": "i"},
                    "pull_request_template": None,
                }
            },
        ),
        "labels": router.get(f"{base}/labels").respond(
            200, json=[{"name": name} for name in labels]
        ),
        "contents": router.get(f"{base}/contents/").respond(
            200,
            json=[
                {"name": name, "type": "file", "size": len(text)}
                for name, text in manifests.items()
            ],
        ),
        "commits": router.get(f"{base}/commits").respond(
            200,
            json=[{"sha": "a"}],
            headers={
                "Link": f'<{API}/repositories/{github_id}/commits?page={commits}>; rel="last"'
            },
        ),
        "pulls": router.get(f"{base}/pulls").respond(
            200,
            json=[
                {
                    "created_at": (now - timedelta(days=5)).isoformat(),
                    "merged_at": (now - timedelta(days=2)).isoformat(),
                    "updated_at": (now - timedelta(days=1)).isoformat(),
                }
            ],
        ),
        "contributors": router.get(f"{base}/contributors").respond(
            200,
            json=[{"login": "a"}],
            headers={"Link": f'<{API}/repositories/{github_id}/contributors?page=57>; rel="last"'},
        ),
        "release": router.get(f"{base}/releases/latest").respond(
            200, json={"published_at": (now - timedelta(days=20)).isoformat()}
        ),
        "issues": router.get(f"{base}/issues").respond(200, json=issues or []),
    }
    for name, text in manifests.items():
        routes[f"file:{name}"] = router.get(f"{base}/contents/{name}").respond(200, text=text)
    return routes


def make_candidate_repo(github_id: int, full_name: str | None = None, **fields: Any) -> Repository:
    full_name = full_name or f"upstream/proj{github_id}"
    owner, name = full_name.split("/")
    defaults: dict[str, Any] = {
        "github_id": github_id,
        "owner_login": owner,
        "name": name,
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "license_spdx": "MIT",
        "stars": 500,
        "pushed_at": timezone.now() - timedelta(days=3),
        "synced_at": timezone.now(),
    }
    return Repository.objects.create(**{**defaults, **fields})


def add_candidate(
    profile: DeveloperProfile,
    repo: Repository,
    *,
    source: str = "language_search",
    query: str = "language:Python",
    rank: int | None = 1,
    seen: datetime | None = None,
) -> RepositoryCandidate:
    seen = seen or timezone.now()
    cand, _ = RepositoryCandidate.objects.get_or_create(
        developer=profile,
        repository=repo,
        defaults={"first_discovered_at": seen, "last_seen_at": seen},
    )
    CandidateDiscovery.objects.create(
        candidate=cand,
        source=source,
        query=query,
        search_rank=rank,
        first_seen_at=seen,
        last_seen_at=seen,
    )
    return cand


def issue_payload(number: int, **extra: Any) -> dict[str, Any]:
    """One item of ``GET /repos/{o}/{r}/issues``."""
    now = timezone.now()
    return {
        "id": 70_000 + number,
        "number": number,
        "title": f"Issue {number}",
        "body": "Something to fix.",
        "labels": [],
        "state": "open",
        "locked": False,
        "assignee": None,
        "assignees": [],
        "comments": 2,
        "html_url": f"https://github.com/o/r/issues/{number}",
        "created_at": (now - timedelta(days=10)).isoformat(),
        "updated_at": (now - timedelta(days=1)).isoformat(),
        **extra,
    }


def make_issue(repo: Repository, number: int, **fields: Any) -> Any:
    from issues.models import Issue

    now = timezone.now()
    defaults: dict[str, Any] = {
        "repository": repo,
        "github_id": repo.github_id * 10_000 + number,
        "number": number,
        "title": f"Issue {number}",
        "html_url": f"https://github.com/{repo.full_name}/issues/{number}",
        "github_created_at": now - timedelta(days=10),
        "github_updated_at": now - timedelta(days=1),
        "analyzed_at": now,
    }
    return Issue.objects.create(**{**defaults, **fields})
