from dataclasses import replace
from datetime import UTC, datetime

import pytest

from services.discovery.queries import (
    DiscoveryInput,
    InterestSignal,
    QueryConfig,
    SkillSignal,
    allocate,
    band_label,
    plan_queries,
)

NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)
QUALIFIERS = "archived:false fork:false is:public pushed:>=2026-04-02 stars:>=20 -user:octocat"
CFG = QueryConfig(
    max_queries=10,
    shares={"language": 2, "skill": 4, "interest": 3, "topic": 1},
    bands=((20, None),),
    max_push_age_days=180,
    min_skill_confidence=0.3,
)


def skill(slug: str, confidence: float = 0.8, *sources: str) -> SkillSignal:
    return SkillSignal(slug, confidence, frozenset(sources or ("language", "dependency")))


def data(skills=(), interests=(), topics=()) -> DiscoveryInput:
    return DiscoveryInput(
        login="octocat",
        skills=tuple(skills),
        interests=tuple(InterestSignal(slug, strength) for slug, strength in interests),
        own_repository_topics=tuple(tuple(t) for t in topics),
        now=NOW,
    )


def cores(plan) -> list[tuple[str, str]]:
    return [(q.source, q.q.removesuffix(f" {QUALIFIERS}")) for q in plan]


def test_python_django_developer_tooling_example() -> None:
    plan = plan_queries(
        data([skill("python", 0.9), skill("django", 0.7)], [("developer-tooling", 0.6)]), CFG
    )
    assert cores(plan) == [
        ("language_search", "language:Python"),
        ("skill_search", "topic:django language:Python"),
        ("interest_search", "topic:developer-tools language:Python"),
        ("interest_search", "topic:developer-tools"),
    ]
    assert all(q.q.endswith(QUALIFIERS) for q in plan)


def test_readme_only_skill_gives_no_query() -> None:
    plan = plan_queries(data([skill("python"), skill("rust", 0.9, "readme")]), CFG)
    assert not any("Rust" in q.q for q in plan)


def test_low_confidence_skill_gives_no_query() -> None:
    assert plan_queries(data([skill("python", 0.2)]), CFG) == []


def test_markup_is_not_a_language_query() -> None:
    plan = plan_queries(data([skill("html", 0.9), skill("python", 0.5)]), CFG)
    assert cores(plan) == [("language_search", "language:Python")]


def test_skill_without_ecosystem_language_is_topic_only() -> None:
    plan = plan_queries(data([skill("docker")]), CFG)
    assert cores(plan) == [("skill_search", "topic:docker")]


def test_framework_paired_with_developers_language_of_its_ecosystem() -> None:
    plan = plan_queries(data([skill("typescript", 0.9), skill("python"), skill("react")]), CFG)
    assert ("skill_search", "topic:react language:TypeScript") in cores(plan)


def test_topic_search_needs_recurring_uncovered_topics() -> None:
    plan = plan_queries(
        data(
            [skill("python")],
            [("developer-tooling", 0.6)],
            topics=[("home-automation", "developer-tools"), ("home-automation",), ("once",)],
        ),
        CFG,
    )
    topic_queries = [c for c in cores(plan) if c[0] == "topic_search"]
    assert topic_queries == [("topic_search", "topic:home-automation")]


def test_budget_split_by_shares() -> None:
    skills = [
        skill(s, 0.9 - i * 0.01)
        for i, s in enumerate(
            [
                "python",
                "typescript",
                "go",
                "rust",
                "java",
                "django",
                "react",
                "fastapi",
                "docker",
                "postgresql",
                "redis",
                "kubernetes",
                "terraform",
            ]
        )
    ]
    interests = [
        ("ai-ml", 0.9),
        ("developer-tooling", 0.8),
        ("web-development", 0.7),
        ("databases", 0.6),
        ("security", 0.5),
    ]
    topics = [("t1", "t2", "t3")] * 2
    plan = plan_queries(data(skills, interests, topics), CFG)
    assert len(plan) == 10
    by_source = [q.source for q in plan]
    assert by_source.count("language_search") == 2
    assert by_source.count("skill_search") == 4
    assert by_source.count("interest_search") == 3
    assert by_source.count("topic_search") == 1


def test_unused_budget_carries_forward_and_wraps() -> None:
    assert allocate(10, CFG.shares, {"language": 5, "skill": 1, "interest": 0, "topic": 0}) == {
        "language": 5,
        "skill": 1,
        "interest": 0,
        "topic": 0,
    }
    assert allocate(10, CFG.shares, {"language": 1, "skill": 9, "interest": 9, "topic": 9}) == {
        "language": 1,
        "skill": 5,
        "interest": 3,
        "topic": 1,
    }


def test_shares_are_weights_when_budget_differs() -> None:
    assert sum(allocate(5, CFG.shares, dict.fromkeys(CFG.shares, 10)).values()) == 5


def test_deterministic() -> None:
    d = data([skill("python"), skill("django")], [("ai-ml", 0.5)], [("cli", "x")] * 2)
    assert plan_queries(d, CFG) == plan_queries(d, CFG)
    assert len({q.key for q in plan_queries(d, CFG)}) == len(plan_queries(d, CFG))


def test_sparse_profile_gives_empty_plan() -> None:
    assert plan_queries(data(), CFG) == []


@pytest.mark.parametrize(
    ("slug", "expected"), [("cpp", 'language:"C++"'), ("csharp", 'language:"C#"')]
)
def test_multi_character_linguist_names_are_quoted(slug: str, expected: str) -> None:
    assert cores(plan_queries(data([skill(slug)]), CFG))[0][1] == expected


BANDED = replace(CFG, max_queries=20, bands=((20, 999), (1000, None)))


def test_every_query_in_every_band() -> None:
    plan = plan_queries(data([skill("python", 0.9), skill("django", 0.7)]), BANDED)
    assert [(q.core, q.key) for q in plan] == [
        # Provenance is the query without qualifiers: one query in both bands.
        ("language:Python", "language:python@0"),
        ("language:Python", "language:python@1"),
        ("topic:django language:Python", "skill:django@0"),
        ("topic:django language:Python", "skill:django@1"),
    ]
    assert plan[0].q == (
        "language:Python archived:false fork:false is:public pushed:>=2026-04-02 "
        "stars:20..999 -user:octocat"
    )
    assert plan[1].q.endswith(" stars:>=1000 -user:octocat")


def test_budget_counts_requests() -> None:
    skills = [skill(s, 0.9 - i * 0.01) for i, s in enumerate(["python", "go", "rust", "java"])]
    interests = [("ai-ml", 0.9), ("developer-tooling", 0.8), ("databases", 0.6)]
    plan = plan_queries(data(skills, interests), replace(BANDED, max_queries=9))
    assert len(plan) == 8  # 9 // 2 = 4 queries, each in both bands
    assert len({q.core.rsplit(" stars:", 1)[0] for q in plan}) == 4


def test_default_settings_plan_ten_queries_in_two_bands() -> None:
    cfg = QueryConfig.from_settings()
    assert cfg.max_queries == 20 and cfg.bands == ((20, 999), (1000, None))
    assert [band_label(b) for b in cfg.bands] == ["20..999", "1000+"]
