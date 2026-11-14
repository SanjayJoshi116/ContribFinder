from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from e2e.builders import make_candidate_repo
from repositories.models import Repository, RepositoryDependency, RepositoryTopic
from services.discovery.filters import (
    FilterConfig,
    eligibility,
    prefilter,
    stored_result_not_code,
    suspected_list,
)
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
        # A suspected list is decided by its dependencies once they were fetched.
        ({"full_name": "vinta/awesome-python"}, None),
        ({"full_name": "vinta/awesome-python", "dependencies_synced_at": NOW}, "not_code"),
        (
            {"full_name": "sindresorhus/awesome-lint", "dependencies_synced_at": NOW, "deps": 1},
            None,
        ),
        ({"primary_language": "", "is_archived": True}, "archived"),
    ],
)
def test_eligibility(fields, reason) -> None:
    fields = dict(fields)
    deps = fields.pop("deps", 0)
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
    repo.has_dependencies = bool(deps)  # type: ignore[attr-defined]  # an annotation
    assert eligibility(repo, now=NOW, cfg=CFG) == reason


def test_no_language_is_not_code() -> None:
    assert check(replace(BASE, primary_language="")) == "not_code"
    assert check(replace(BASE, primary_language=""), check_stars=False) == "not_code"


@pytest.mark.parametrize(
    "change",
    [
        {"full_name": "vinta/awesome-python"},
        {"full_name": "sindresorhus/Awesome"},
        {"topics": ("python", "Awesome-List")},
        {"topics": ("books",)},
    ],
)
def test_suspected_lists_pass_the_search_filter(change) -> None:
    """Never analyzed: its analysis decides whether it has code (manifest dependencies)."""
    repo = replace(BASE, **change)
    assert check(repo) is None
    assert suspected_list(repo.full_name, repo.topics, CFG)


def test_biggest_lists_carry_generic_topics_by_default() -> None:
    # public-apis and free-programming-books are tagged only `list` / `lists` / `books`.
    topics = FilterConfig.from_settings().excluded_topics
    assert {"list", "lists", "books"} <= topics


def test_library_tagged_list_passes_search() -> None:
    library = replace(BASE, full_name="x/linked-list", topics=("books", "data-structures"))
    assert suspected_list(library.full_name, library.topics, CFG)
    assert check(library) is None  # never analyzed: its dependencies decide


def test_awesome_inside_a_name_is_code() -> None:
    assert check(replace(BASE, full_name="x/make-awesome", topics=("list-view",))) is None


def test_repository_rules_win_over_not_code() -> None:
    assert check(replace(BASE, primary_language="", is_archived=True)) == "archived"


def stored(full_name: str = "EbookFoundation/free-programming-books", **fields) -> Repository:
    return make_candidate_repo(
        2,
        full_name,
        **{
            "license_spdx": "CC-BY-4.0",
            "pushed_at": NOW - timedelta(days=3),
            "dependencies_synced_at": timezone.now(),
            **fields,
        },
    )


@pytest.mark.django_db
def test_stored_result_not_code() -> None:
    result = replace(BASE, full_name="vinta/awesome-python")
    repo = stored(result.full_name)
    assert stored_result_not_code(result, repo, CFG)  # an analysis found no dependencies
    RepositoryDependency.objects.create(
        repository=repo, ecosystem="pypi", name="requests", manifest_path="requirements.txt"
    )
    assert not stored_result_not_code(result, repo, CFG)


@pytest.mark.django_db
def test_stored_result_not_a_list_reads_no_dependencies(django_assert_num_queries) -> None:
    repo = stored("encode/httpx")
    with django_assert_num_queries(0):
        assert not stored_result_not_code(BASE, repo, CFG)


@pytest.mark.django_db
def test_rejected_stored_repository_reads_no_dependencies(django_assert_num_queries) -> None:
    repo = stored("vinta/awesome-python", is_archived=True)  # not annotated
    with django_assert_num_queries(0):
        reason = prefilter(repo, login="octocat", owned=set(), now=NOW, cfg=CFG, check_stars=False)
        assert reason == "archived"


@pytest.mark.django_db
def test_list_already_in_pool_becomes_ineligible() -> None:
    repo = stored()
    assert eligibility(repo, now=NOW, cfg=CFG) is None
    RepositoryTopic.objects.create(repository=repo, topic="books")
    assert eligibility(repo, now=NOW, cfg=CFG) == "not_code"
    RepositoryDependency.objects.create(
        repository=repo, ecosystem="pypi", name="requests", manifest_path="requirements.txt"
    )
    assert eligibility(repo, now=NOW, cfg=CFG) is None  # code evidence wins
