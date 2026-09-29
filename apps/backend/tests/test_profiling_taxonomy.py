from collections import Counter

import pytest

from services.profiling import taxonomy as t


def test_slugs_unique_and_categories_valid() -> None:
    slugs = [s.slug for s in t.SKILLS]
    assert len(slugs) == len(set(slugs))
    assert {s.category for s in t.SKILLS} == {
        "language",
        "framework",
        "library",
        "database",
        "cloud",
        "devops",
        "tool",
    }
    assert len(t.SKILLS) >= 150
    assert len({i.slug for i in t.INTERESTS}) == len(t.INTERESTS) >= 14


def _collisions(pairs) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = {}
    for key, slug in pairs:
        owners.setdefault(key, set()).add(slug)
    return {k: v for k, v in owners.items() if len(v) > 1}


def test_no_phrase_collisions_between_skills() -> None:
    pairs = [(a, s.slug) for s in t.SKILLS for a in (*s.aliases, *s.ambiguous)]
    assert _collisions(pairs) == {}


def test_no_topic_collisions_between_skills() -> None:
    assert _collisions((topic, s.slug) for s in t.SKILLS for topic in t._skill_topics(s)) == {}


def test_no_icon_collisions_between_skills() -> None:
    pairs = [
        (t.icon_token(v), s.slug)
        for s in t.SKILLS
        for v in (s.slug, s.name, *s.aliases, *s.ambiguous, *s.icons)
    ]
    assert _collisions(pairs) == {}


def test_no_dependency_collisions_between_skills() -> None:
    pairs = [
        ((eco, t.normalize_dependency(eco, dep)), s.slug)
        for s in t.SKILLS
        for eco, deps in s.deps.items()
        for dep in deps
    ]
    assert _collisions(pairs) == {}


def test_no_interest_topic_collisions() -> None:
    counts = Counter(topic for i in t.INTERESTS for topic in i.topics)
    assert [topic for topic, n in counts.items() if n > 1] == []


def test_implied_interests_exist() -> None:
    for skill in t.SKILLS:
        for slug in skill.implies_interests:
            assert slug in t.INTERESTS_BY_SLUG, (skill.slug, slug)


def test_postgresql_resolves_from_every_vocabulary() -> None:
    assert t.PLAIN_PHRASES["postgres"] == "postgresql"
    assert t.skill_for_topic("postgresql") == "postgresql"
    assert t.skill_for_dependency("pypi", "psycopg") == "postgresql"
    assert t.skill_for_dependency("pypi", "psycopg2_binary") == "postgresql"
    assert t.skill_for_icon("postgresql") == "postgresql"


@pytest.mark.parametrize(
    ("ecosystem", "name", "slug"),
    [
        ("pypi", "Django", "django"),
        ("pypi", "djangorestframework", "django-rest-framework"),
        ("pypi", "google-cloud-storage", "gcp"),
        ("npm", "@nestjs/core", "nestjs"),
        ("npm", "@aws-sdk/client-s3", "aws"),
        ("go", "github.com/aws/aws-sdk-go-v2", "aws"),
        ("go", "github.com/jackc/pgx/v5", "postgresql"),
        ("cargo", "actix-web", "actix"),
        ("maven", "org.springframework.boot:spring-boot-starter-web", "spring"),
        ("gradle", "org.springframework.boot:spring-boot-starter-web", "spring"),
    ],
)
def test_dependency_lookup(ecosystem: str, name: str, slug: str) -> None:
    assert t.skill_for_dependency(ecosystem, name) == slug


@pytest.mark.parametrize(
    ("token", "slug"),
    [
        ("nodedotjs", "nodejs"),
        ("c%2B%2B", "cpp"),
        ("cplusplus", "cpp"),
        ("csharp", "csharp"),
        ("amazonaws", "aws"),
        ("py", "python"),
        ("k8s", "kubernetes"),
        ("dotnet", "dotnet"),
    ],
)
def test_icon_lookup(token: str, slug: str) -> None:
    assert t.skill_for_icon(token) == slug


def test_linguist_lookup() -> None:
    assert t.skill_for_linguist("Jupyter Notebook") == "jupyter"
    assert t.skill_for_linguist("Dockerfile") == "docker"
    assert t.skill_for_linguist("HCL") == "terraform"
    assert t.skill_for_linguist("Makefile") is None


def test_unknown_terms_resolve_to_nothing() -> None:
    assert "foobarframework" not in t.PLAIN_PHRASES
    assert t.skill_for_topic("foobarframework") is None
    assert t.skill_for_dependency("pypi", "foobarframework") is None
    assert t.skill_for_icon("foobarframework") is None


def test_dotnet_does_not_claim_generic_net_topic() -> None:
    assert t.skill_for_topic("net") is None
    assert t.skill_for_topic("dotnet") == "dotnet"
