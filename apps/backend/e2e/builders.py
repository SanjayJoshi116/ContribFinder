"""Database builders for seeded data: shared by ``e2e_seed`` (browser-test data) and the
backend tests, so a change here is exercised by both. Imports nothing from ``tests``."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

from developers.models import DeveloperProfile
from issues.models import Issue
from repositories.models import CandidateDiscovery, Repository, RepositoryCandidate
from services.repositories.staleness import PART_FIELDS


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
        "primary_language": "Python",
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
    discovery_seen: datetime | None = None,
) -> RepositoryCandidate:
    """``discovery_seen`` (default ``seen``): when the discovery record was last seen. A run
    prunes records it did not see again, so a record standing for "found by this run" needs a
    time after the run starts."""
    seen = seen or timezone.now()
    record_seen = discovery_seen or seen
    # As discovery: a candidate is seen whenever one of its records is, and found no later.
    earliest, latest = min(seen, record_seen), max(seen, record_seen)
    cand, created = RepositoryCandidate.objects.get_or_create(
        developer=profile,
        repository=repo,
        defaults={"first_discovered_at": earliest, "last_seen_at": latest},
    )
    if not created and cand.last_seen_at < latest:
        cand.last_seen_at = latest
        cand.save(update_fields=["last_seen_at"])
    CandidateDiscovery.objects.create(
        candidate=cand,
        source=source,
        query=query,
        search_rank=rank,
        first_seen_at=seen,
        last_seen_at=record_seen,
    )
    return cand


def make_issue(repo: Repository, number: int, **fields: Any) -> Issue:
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


def fresh_repo(github_id: int = 7, full_name: str = "encode/httpx", **fields: Any) -> Repository:
    """An analyzed, recommendable repository whose data is all fresh."""
    now = timezone.now()
    defaults = {
        "lifecycle": "recommendable",
        "is_eligible": True,
        **{field: now for field in PART_FIELDS.values()},
    }
    return make_candidate_repo(github_id, full_name, **{**defaults, **fields})
