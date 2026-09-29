from django.conf import settings

from services.profiling.interests import detect_interests, interest_evidence

from .profiling_fixtures import contribution, profile, repo


def detect(p):
    return {
        d.slug: d
        for d in detect_interests(
            p,
            settings.INTEREST_EVIDENCE_WEIGHTS,
            decay=0.5,
            cap=0.99,
            min_strength=settings.INTEREST_MIN_STRENGTH,
        )
    }


def test_synonyms_resolve_to_one_interest() -> None:
    p = profile(
        readme="I work on deep learning.",
        owned=(
            repo(description="A machine learning pipeline"),
            repo(topics=("llm",)),
        ),
    )
    found = detect(p)
    assert list(found) == ["ai-ml"]
    assert sorted(e.source for e in found["ai-ml"].evidence) == [
        "readme",
        "repo_description",
        "topic",
    ]


def test_topic_evidence_names_repository() -> None:
    r = repo(topics=("developer-tools",))
    [evidence] = interest_evidence(profile(owned=(r,)))
    assert (evidence.key, evidence.source, evidence.repository_id, evidence.detail) == (
        "developer-tooling",
        "topic",
        r.id,
        '"developer-tools"',
    )


def test_word_boundary() -> None:
    assert interest_evidence(profile(owned=(repo(description="Helps maintain dotfiles"),))) == []


def test_contributed_repository() -> None:
    c = contribution(prs=1, topics=("security",), description="Security scanner")
    [evidence] = interest_evidence(profile(contributions=(c,)))
    assert (evidence.key, evidence.source, evidence.repository_id) == (
        "security",
        "contribution",
        c.repo.id,
    )


def test_forks_ignored() -> None:
    assert interest_evidence(profile(owned=(repo(topics=("security",), is_fork=True),))) == []


def test_single_weak_mention_excluded() -> None:
    assert "mobile-development" not in detect(profile(readme="I once built a mobile app."))


def test_repeated_across_repositories_included_and_ordered() -> None:
    p = profile(
        readme="Into security.",
        owned=tuple(repo(topics=("developer-tools",)) for _ in range(3)),
    )
    found = detect(p)
    assert "developer-tooling" in found
    assert next(iter(found)) == "developer-tooling"  # ordered by strength
    assert "security" not in found  # a single README phrase stays below the threshold
