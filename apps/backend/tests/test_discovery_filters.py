from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from repositories.models import Repository, RepositoryTopic
from services.discovery.filters import FilterConfig, eligibility, prefilter
from services.github.client import GitHubRepo

NOW = datetime(2026, 9, 29, tzinfo=UTC)
CFG = FilterConfig(
    min_stars=20, max_push_age_days=180, excluded_topics=frozenset({"awesome-list", "books"})
)

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
        ({"primary_language": ""}, "not_code"),
        ({"full_name": "vinta/awesome-python"}, "not_code"),
        ({"primary_language": "", "is_archived": True}, "archived"),
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
        "primary_language": "Python",
        "pushed_at": NOW - timedelta(days=3),
        "synced_at": timezone.now(),
    }
    repo = Repository(**{**defaults, **fields})
    assert eligibility(repo, now=NOW, cfg=CFG) == reason


@pytest.mark.parametrize(
    "change",
    [
        {"full_name": "vinta/awesome-python"},
        {"full_name": "sindresorhus/Awesome"},
        {"topics": ("python", "Awesome-List")},
        {"topics": ("books",)},
        {"primary_language": ""},
    ],
)
def test_lists_and_docs_are_not_code(change) -> None:
    assert check(replace(BASE, **change)) == "not_code"
    assert check(replace(BASE, **change), check_stars=False) == "not_code"  # interacted too


def test_awesome_inside_a_name_is_code() -> None:
    assert check(replace(BASE, full_name="x/make-awesome", topics=("list-view",))) is None


def test_repository_rules_win_over_not_code() -> None:
    assert check(replace(BASE, primary_language="", is_archived=True)) == "archived"


@pytest.mark.django_db
def test_list_already_in_pool_becomes_ineligible() -> None:
    repo = Repository.objects.create(
        github_id=2,
        owner_login="EbookFoundation",
        name="free-programming-books",
        full_name="EbookFoundation/free-programming-books",
        html_url="https://github.com/EbookFoundation/free-programming-books",
        license_spdx="CC-BY-4.0",
        primary_language="Python",
        pushed_at=NOW - timedelta(days=3),
        synced_at=timezone.now(),
    )
    assert eligibility(repo, now=NOW, cfg=CFG) is None
    RepositoryTopic.objects.create(repository=repo, topic="books")
    assert eligibility(repo, now=NOW, cfg=CFG) == "not_code"
