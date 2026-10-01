"""A repository's technologies from its stored data (spec: recommendation-engine; design D2).

Pure: the same catalog that builds the developer profile maps a repository's languages, topics
and dependencies to skill slugs, so both sides of a match speak the same vocabulary.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from services.profiling.taxonomy import (
    SKILLS_BY_SLUG,
    skill_for_dependency,
    skill_for_linguist,
    skill_for_topic,
)

LANGUAGE_SOURCE = "language"
TOPIC_SOURCE = "topic"
DEPENDENCY_SOURCE = "dependency"


@dataclass(frozen=True)
class Tech:
    slug: str
    name: str
    category: str
    weight: float  # how strongly the repository uses it, 0..1
    sources: tuple[str, ...]
    share: float | None = None  # byte share, for languages


def repository_technologies(
    languages: Iterable[tuple[str, int]],
    topics: Iterable[str],
    dependencies: Iterable[tuple[str, str]],
    source_weights: Mapping[str, float],
) -> dict[str, Tech]:
    """``{slug: Tech}``. Languages weigh their byte share of the whole repository (unmapped
    languages stay in the denominator); topics and dependencies weigh ``source_weights``. A
    slug found by several sources keeps the highest weight and every source."""
    weights: dict[str, float] = {}
    sources: dict[str, list[str]] = {}
    shares: dict[str, float] = {}

    def add(slug: str, weight: float, source: str) -> None:
        weights[slug] = max(weights.get(slug, 0.0), weight)
        if source not in sources.setdefault(slug, []):
            sources[slug].append(source)

    language_list = list(languages)
    total = sum(size for _, size in language_list)
    for language, size in language_list:
        slug = skill_for_linguist(language)
        if slug is None or total <= 0:
            continue
        share = size / total
        shares[slug] = shares.get(slug, 0.0) + share
        add(slug, shares[slug], LANGUAGE_SOURCE)
    for topic in topics:
        if slug := skill_for_topic(topic):
            add(slug, source_weights[TOPIC_SOURCE], TOPIC_SOURCE)
    for ecosystem, name in dependencies:
        if slug := skill_for_dependency(ecosystem, name):
            add(slug, source_weights[DEPENDENCY_SOURCE], DEPENDENCY_SOURCE)

    result: dict[str, Tech] = {}
    for slug, weight in weights.items():
        skill = SKILLS_BY_SLUG.get(slug)
        if skill is None:
            continue
        result[slug] = Tech(
            slug=slug,
            name=skill.name,
            category=skill.category,
            weight=round(min(1.0, weight), 4),
            sources=tuple(sources[slug]),
            share=round(shares[slug], 4) if slug in shares else None,
        )
    return result
