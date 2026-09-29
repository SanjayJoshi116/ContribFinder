from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from repositories.models import Repository
from services.discovery.filters import FilterConfig, eligibility, prefilter
from services.github.client import GitHubRepo

NOW = datetime(2026, 9, 29, tzinfo=UTC)
CFG = FilterConfig(min_stars=20, max_push_age_days=180)

BASE = GitHubRepo(
    github_id=1,
    owner_login="encode",
    name="httpx",
    full_name="encode/httpx",
    description="",
    html_url="https://github.com/encode/httpx",
    default_branch="master",
    stars=500,
    forks=10,
    open_issues=3,
    primary_language="Python",
    license_spdx="BSD-3-Clause",
    is_fork=False,
    is_archived=False,
    created_at=None,
    updated_at=None,
    pushed_at=NOW - timedelta(days=3),
    topics=(),
)


def check(repo: GitHubRepo, **kw) -> str | None:
    return prefilter(repo, login="octocat", owned=set(), now=NOW, cfg=CFG, **kw)


def test_passes() -> None:
    assert check(BASE) is None


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"is_archived": True}, "archived"),
        ({"is_fork": True}, "fork"),
        ({"pushed_at": NOW - timedelta(days=181)}, "inactive"),
        ({"pushed_at": None}, "inactive"),
        ({"license_spdx": ""}, "no_license"),
        ({"stars": 19}, "few_stars"),
        ({"owner_login": "OctoCat"}, "own_repository"),
    ],
)
def test_prefilter_reasons(change, reason: str) -> None:
    assert check(replace(BASE, **change)) == reason


def test_noassertion_counts_as_licensed() -> None:
    assert check(replace(BASE, license_spdx="NOASSERTION")) is None


def test_owned_by_full_name() -> None:
    owned = {"encode/httpx"}
    assert prefilter(BASE, login="x", owned=owned, now=NOW, cfg=CFG) == "own_repository"


def test_stars_not_checked_for_previously_interacted() -> None:
    assert check(replace(BASE, stars=0), check_stars=False) is None
    assert check(replace(BASE, stars=0, is_archived=True), check_stars=False) == "archived"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({}, None),
        ({"is_archived": True}, "archived"),
        ({"license_spdx": ""}, "no_license"),
        ({"lifecycle": "failed"}, "repository_unavailable"),
        ({"stars": 0}, None),  # stars are a search-time rule only
    ],
)
def test_eligibility(fields, reason) -> None:
    defaults = {
        "github_id": 1,
        "owner_login": "encode",
        "name": "httpx",
        "full_name": "encode/httpx",
        "html_url": "https://github.com/encode/httpx",
        "license_spdx": "MIT",
        "pushed_at": NOW - timedelta(days=3),
        "synced_at": timezone.now(),
    }
    repo = Repository(**{**defaults, **fields})
    assert eligibility(repo, now=NOW, cfg=CFG) == reason
