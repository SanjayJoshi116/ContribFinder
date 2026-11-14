from collections import Counter
from typing import Any

from services.profiling.collectors import (
    contribution_skills,
    dependency_skills,
    language_skills,
    topic_skills,
)

from .profiling_fixtures import contribution, profile, repo


def keys(evidence) -> Counter[str]:
    return Counter(e.key for e in evidence)


def test_language_evidence_per_repository() -> None:
    repos = tuple(repo(languages={"Python": 900, "Shell": 100}) for _ in range(8))
    evidence = language_skills(profile(owned=repos), 0.10)
    assert keys(evidence)["python"] == 8
    assert {e.repository_id for e in evidence if e.key == "python"} == {r.id for r in repos}
    assert all(e.source == "language" for e in evidence)
    assert evidence[0].detail == "Python · 90% of code"


def test_minor_language_ignored_primary_kept() -> None:
    r = repo(languages={"Python": 9800, "Shell": 200, "Go": 50}, primary_language="Go")
    assert set(keys(language_skills(profile(owned=(r,)), 0.10))) == {"python", "go"}


def test_own_repository_sources_read_only_owned_repositories() -> None:
    """`features.OWN_REPOSITORY_SOURCES` count as "your repositories" (MAT-2): their
    collectors must never pass a repository the developer only contributed to."""
    from services.matching.features import OWN_REPOSITORY_SOURCES

    stack: dict[str, Any] = {
        "languages": {"Python": 900},
        "topics": ("django",),
        "deps": (("pypi", "django", "requirements.txt"),),
    }
    owned = repo(**stack)
    p = profile(owned=(owned,), contributions=(contribution(prs=3, **stack),))
    collected = language_skills(p, 0.10) + topic_skills(p) + dependency_skills(p)
    assert {e.source for e in collected} == set(OWN_REPOSITORY_SOURCES)
    assert {e.repository_id for e in collected} == {owned.id}


def test_unmapped_language_ignored() -> None:
    r = repo(languages={"Makefile": 100})
    assert language_skills(profile(owned=(r,)), 0.10) == []


def test_forks_provide_no_evidence() -> None:
    fork = repo(
        languages={"Rust": 100},
        topics=("django",),
        is_fork=True,
        deps=[("cargo", "tokio", "Cargo.toml")],
    )
    p = profile(owned=(fork,))
    assert language_skills(p, 0.1) == topic_skills(p) == dependency_skills(p) == []


def test_topic_evidence() -> None:
    r = repo(topics=("django", "rest-api"))
    [evidence] = topic_skills(profile(owned=(r,)))
    assert (evidence.key, evidence.repository_id, evidence.detail) == (
        "django",
        r.id,
        '"django"',
    )


def test_dependency_evidence_one_per_skill_and_repository() -> None:
    r = repo(
        deps=[
            ("pypi", "djangorestframework", "pyproject.toml"),
            ("pypi", "celery", "pyproject.toml"),
            ("pypi", "psycopg", "pyproject.toml"),
            ("pypi", "psycopg-binary", "pyproject.toml"),
            ("pypi", "unknown-thing", "pyproject.toml"),
        ]
    )
    evidence = dependency_skills(profile(owned=(r,)))
    assert keys(evidence) == {"django-rest-framework": 1, "celery": 1, "postgresql": 1}
    drf = next(e for e in evidence if e.key == "django-rest-framework")
    assert drf.detail == "pyproject.toml: djangorestframework"


def test_merged_pull_request_evidence() -> None:
    c = contribution(prs=1, full_name="pallets/flask", languages={"Python": 100})
    [evidence] = contribution_skills(profile(contributions=(c,)), 0.1, 3)
    assert (evidence.key, evidence.source, evidence.repository_id) == (
        "python",
        "pull_request",
        c.repo.id,
    )
    assert evidence.detail == "1 merged pull request"


def test_repeated_contribution() -> None:
    c = contribution(prs=4, languages={"Go": 100})
    evidence = contribution_skills(profile(contributions=(c,)), 0.1, 3)
    assert Counter(e.source for e in evidence) == {"pull_request": 1, "repeated_contribution": 1}


def test_pushes_are_commit_evidence_and_topics_attribute_skills() -> None:
    c = contribution(pushes=2, languages={"TypeScript": 100}, topics=("react",))
    evidence = contribution_skills(profile(contributions=(c,)), 0.1, 3)
    assert {(e.key, e.source) for e in evidence} == {("typescript", "commit"), ("react", "commit")}
    assert evidence[0].detail.startswith("2 recent pushes")


def test_no_contributions() -> None:
    assert contribution_skills(profile(), 0.1, 3) == []
