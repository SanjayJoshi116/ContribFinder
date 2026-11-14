"""Repository search queries from the developer profile (FR-REPO-001, design D3).

Pure: the same ``DiscoveryInput`` and ``QueryConfig`` always give the same queries in the
same order. Nothing here touches the database or GitHub.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings

from repositories.models import DiscoverySource
from services.profiling.taxonomy import INTERESTS_BY_SLUG, MARKUP, SKILLS_BY_SLUG, SkillDef

STRATEGIES = ("language", "skill", "interest", "topic")
SOURCE_BY_STRATEGY = {
    "language": DiscoverySource.LANGUAGE_SEARCH,
    "skill": DiscoverySource.SKILL_SEARCH,
    "interest": DiscoverySource.INTEREST_SEARCH,
    "topic": DiscoverySource.TOPIC_SEARCH,
}
# Languages a dependency ecosystem implies, so a framework query can be paired with the
# developer's language for it (Django → Python). Ordered by how typical they are.
ECOSYSTEM_LANGUAGES: dict[str, tuple[str, ...]] = {
    "pypi": ("python",),
    "npm": ("typescript", "javascript"),
    "go": ("go",),
    "cargo": ("rust",),
    "jvm": ("java", "kotlin", "scala"),
}
# An owned-repository topic must recur this often to become a topic search.
TOPIC_MIN_REPOSITORIES = 2
LANGUAGE = "language"


@dataclass(frozen=True)
class SkillSignal:
    slug: str
    confidence: float
    sources: frozenset[str]


@dataclass(frozen=True)
class InterestSignal:
    slug: str
    strength: float


@dataclass(frozen=True)
class DiscoveryInput:
    login: str
    skills: tuple[SkillSignal, ...]
    interests: tuple[InterestSignal, ...]
    own_repository_topics: tuple[tuple[str, ...], ...]  # per owned non-fork repository
    now: datetime


Band = tuple[int, int | None]  # stars [low, high]; high None = no upper bound


@dataclass(frozen=True)
class QueryConfig:
    max_queries: int  # search requests: one query in one band
    shares: Mapping[str, int]
    bands: tuple[Band, ...]
    max_push_age_days: int
    min_skill_confidence: float

    @classmethod
    def from_settings(cls) -> QueryConfig:
        return cls(
            max_queries=settings.DISCOVERY_MAX_QUERIES,
            shares=dict(settings.DISCOVERY_QUERY_SHARES),
            bands=star_bands(),
            max_push_age_days=settings.DISCOVERY_MAX_PUSH_AGE_DAYS,
            min_skill_confidence=settings.DISCOVERY_MIN_SKILL_CONFIDENCE,
        )


def default_star_bands(min_stars: int) -> list[list[int | None]]:
    return [[min_stars, 999], [1000, None]] if min_stars < 1000 else [[min_stars, None]]


def configured_star_bands() -> list[list[int | None]]:
    """``DISCOVERY_STAR_BANDS`` as configured, or derived from ``DISCOVERY_MIN_STARS`` when
    unset (read at call time, so overriding the minimum moves the default bands too)."""
    bands: list[list[int | None]] | None = settings.DISCOVERY_STAR_BANDS
    return bands if bands is not None else default_star_bands(settings.DISCOVERY_MIN_STARS)


def star_bands() -> tuple[Band, ...]:
    return tuple(
        (int(low or 0), None if high is None else int(high))
        for low, high in configured_star_bands()
    )


def band_label(band: Band) -> str:
    low, high = band
    return f"{low}..{high}" if high is not None else f"{low}+"


def band_of(stars: int, bands: Sequence[Band]) -> Band | None:
    """The band whose range holds ``stars`` (an open high has no limit), or None."""
    for band in bands:
        low, high = band
        if low <= stars and (high is None or stars <= high):
            return band
    return None


def _stars(band: Band) -> str:
    low, high = band
    return f"stars:{low}..{high}" if high is not None else f"stars:>={low}"


@dataclass(frozen=True)
class PlannedQuery:
    source: str
    q: str  # full query text sent to GitHub, qualifiers included
    key: str  # stable id of the request within a plan (query and band), for resuming
    core: str  # the query without the qualifiers (band included): stored as provenance
    # The star band's label with more than one band, "" with one (plans stored before bands
    # were recorded load with "" too).
    band: str = ""

    def as_json(self) -> dict[str, str]:
        return {
            "source": self.source,
            "q": self.q,
            "key": self.key,
            "core": self.core,
            "band": self.band,
        }


def plan_queries(data: DiscoveryInput, cfg: QueryConfig) -> list[PlannedQuery]:
    skills = _qualifying_skills(data.skills, cfg.min_skill_confidence)
    languages = [s for s in skills if _category(s) == LANGUAGE and s.slug not in MARKUP]
    top_language = languages[0].slug if languages else None

    cores: dict[str, list[tuple[str, str]]] = {}
    searched_topic: dict[str, str] = {}  # skill and interest query key -> the topic it searches
    seen: set[str] = set()

    def add(strategy: str, key: str, core: str, topic: str = "") -> None:
        if core not in seen:
            seen.add(core)
            cores.setdefault(strategy, []).append((key, core))
            if topic:
                searched_topic[key] = topic

    for skill in languages:
        if linguist := _linguist(SKILLS_BY_SLUG[skill.slug]):
            add("language", f"language:{skill.slug}", f"language:{_quote(linguist)}")

    for skill in skills:
        definition = SKILLS_BY_SLUG[skill.slug]
        if definition.category == LANGUAGE:
            continue
        topic = _primary_topic(definition)
        language = _paired_language(definition, languages)
        core = f"topic:{topic}" + (f" language:{_quote(language)}" if language else "")
        add("skill", f"skill:{skill.slug}", core, topic)

    interests = sorted(data.interests, key=lambda i: (-i.strength, i.slug))
    top_language_name = _linguist(SKILLS_BY_SLUG[top_language]) if top_language else None
    interest_topics = [
        (i.slug, INTERESTS_BY_SLUG[i.slug].topics[0])
        for i in interests
        if i.slug in INTERESTS_BY_SLUG and INTERESTS_BY_SLUG[i.slug].topics
    ]
    for slug, topic in interest_topics:
        suffix = f" language:{_quote(top_language_name)}" if top_language_name else ""
        add("interest", f"interest:{slug}", f"topic:{topic}{suffix}", topic)
    if top_language_name:
        # Language-free variants come last and are only used when budget remains.
        for slug, topic in interest_topics:
            add("interest", f"interest:{slug}:any", f"topic:{topic}", topic)

    counts = Counter(t.lower() for topics in data.own_repository_topics for t in set(topics))
    recurring = [
        topic
        for topic, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= TOPIC_MIN_REPOSITORIES
    ]

    # Every query runs in every star band (design D1, D2): the budget counts requests, and a
    # query is planned in all bands or not at all. With one band the plan is the pre-band one.
    budget = cfg.max_queries // len(cfg.bands)
    available = {s: len(cores.get(s, [])) for s in STRATEGIES}

    # A topic counts as covered only by a skill or interest query the budget plans (change
    # services-discovery-review-fixes, D1; CR5-1). Start with every such topic covered and
    # allocate until the covered set is the one the quotas plan. Each round the topic list can
    # only grow, so less budget wraps back and the covered set can only shrink: it ends within
    # as many rounds as there are topics. A topic query never repeats a planned core: a planned
    # skill or interest query covers its topic.
    covered = set(searched_topic.values())
    while True:
        cores["topic"] = [(f"topic:{t}", f"topic:{t}") for t in recurring if t not in covered]
        quotas = allocate(budget, cfg.shares, {**available, "topic": len(cores["topic"])})
        planned = {
            searched_topic[key]
            for s in ("skill", "interest")
            for key, _ in cores.get(s, [])[: quotas[s]]
        }
        if planned == covered:
            break
        covered = planned
    banded = len(cfg.bands) > 1
    return [
        PlannedQuery(
            SOURCE_BY_STRATEGY[strategy],
            f"{core} {_qualifiers(data, cfg, band)}",
            f"{key}@{index}" if banded else key,
            core,
            band_label(band) if banded else "",
        )
        for strategy in STRATEGIES
        for key, core in cores.get(strategy, [])[: quotas[strategy]]
        for index, band in enumerate(cfg.bands)
    ]


def allocate(
    budget: int, shares: Mapping[str, int], available: Mapping[str, int]
) -> dict[str, int]:
    """Split ``budget`` by ``shares`` (weights, in ``STRATEGIES`` order), never giving a
    strategy more than it has available. Unused slots pass to later strategies, then wrap
    around once to earlier ones."""
    total_share = sum(shares.get(s, 0) for s in STRATEGIES)
    quotas = dict.fromkeys(STRATEGIES, 0)
    if budget <= 0 or total_share <= 0:
        return quotas
    base = {s: budget * shares.get(s, 0) // total_share for s in STRATEGIES}
    leftover = budget - sum(base.values())
    # Largest remainder, ties in strategy order. The leftover is the sum of the fractional
    # parts, so it never exceeds the strategies with one (all of positive share).
    by_remainder = sorted(
        (s for s in STRATEGIES if shares.get(s, 0) > 0),
        key=lambda s: (-(budget * shares.get(s, 0) % total_share), STRATEGIES.index(s)),
    )
    for s in by_remainder[:leftover]:
        base[s] += 1
    carry = 0
    for s in STRATEGIES:
        want = base[s] + carry
        quotas[s] = min(want, available.get(s, 0))
        carry = want - quotas[s]
    for s in STRATEGIES:
        extra = min(carry, available.get(s, 0) - quotas[s])
        quotas[s] += extra
        carry -= extra
    return quotas


def _qualifying_skills(skills: Sequence[SkillSignal], min_confidence: float) -> list[SkillSignal]:
    """Skills known to the catalog, confident enough, and backed by more than a README."""
    return sorted(
        (
            s
            for s in skills
            if s.slug in SKILLS_BY_SLUG
            and s.confidence >= min_confidence
            and s.sources - {"readme"}
        ),
        key=lambda s: (-s.confidence, s.slug),
    )


def _category(skill: SkillSignal) -> str:
    return SKILLS_BY_SLUG[skill.slug].category


def _linguist(skill: SkillDef) -> str | None:
    return skill.linguist[0] if skill.linguist else None


def _primary_topic(skill: SkillDef) -> str:
    return skill.topics[0] if skill.topics else skill.slug


def _paired_language(skill: SkillDef, languages: Sequence[SkillSignal]) -> str | None:
    """The developer's strongest language among those the skill's ecosystems imply."""
    implied = {lang for eco in skill.deps for lang in ECOSYSTEM_LANGUAGES.get(eco, ())}
    for language in languages:  # sorted by confidence
        if language.slug in implied:
            return _linguist(SKILLS_BY_SLUG[language.slug])
    return None


def _quote(value: str) -> str:
    return value if re.fullmatch(r"[A-Za-z0-9-]+", value) else f'"{value}"'


def _qualifiers(data: DiscoveryInput, cfg: QueryConfig, band: Band) -> str:
    pushed = (data.now - timedelta(days=cfg.max_push_age_days)).date().isoformat()
    return (
        f"archived:false fork:false is:public pushed:>={pushed} {_stars(band)} -user:{data.login}"
    )
