"""Interest detection (spec: interest-detection). Synonym phrases and topic mappings from the
catalog; strength uses the same diminishing-returns rule as skill confidence."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from .confidence import compute_confidence
from .inputs import Evidence, ProfileInput, RepoInput
from .taxonomy import INTERESTS, interest_for_topic
from .text import PhraseMatcher, plain_text

SYNONYM_MATCHER = PhraseMatcher({s: i.slug for i in INTERESTS for s in i.synonyms})


@dataclass(frozen=True)
class DetectedInterest:
    slug: str
    strength: float
    evidence: tuple[Evidence, ...]


def _repo_evidence(
    repo: RepoInput, *, contributed: bool, observed_at: datetime | None
) -> list[Evidence]:
    """Topic and description evidence for one repository: one record per interest and kind
    for owned repositories, one record per interest for contributed ones."""
    found: dict[tuple[str, str], Evidence] = {}
    for topic in repo.topics:
        if slug := interest_for_topic(topic):
            source = "contribution" if contributed else "topic"
            found.setdefault(
                (slug, source), Evidence(slug, source, repo.id, f'"{topic}"', observed_at)
            )
    for slug, phrase in SYNONYM_MATCHER.find(repo.description).items():
        source = "contribution" if contributed else "repo_description"
        detail = f'Mentions "{phrase}"'
        found.setdefault((slug, source), Evidence(slug, source, repo.id, detail, observed_at))
    return list(found.values())


def interest_evidence(profile: ProfileInput) -> list[Evidence]:
    evidence = [
        Evidence(slug, "readme", None, f'Mentions "{phrase}"', profile.readme_observed_at)
        for slug, phrase in SYNONYM_MATCHER.find(plain_text(profile.readme)).items()
    ]
    for repo in profile.own_work:
        evidence += _repo_evidence(repo, contributed=False, observed_at=repo.pushed_at)
    for contribution in profile.contributions:
        evidence += _repo_evidence(
            contribution.repo, contributed=True, observed_at=contribution.observed_at
        )
    return evidence


def detect_interests(
    profile: ProfileInput,
    weights: Mapping[str, float],
    *,
    decay: float,
    cap: float,
    min_strength: float,
) -> list[DetectedInterest]:
    grouped: dict[str, list[Evidence]] = defaultdict(list)
    for item in interest_evidence(profile):
        grouped[item.key].append(item)

    detected = []
    for slug, items in grouped.items():
        strength = compute_confidence(items, weights, decay=decay, cap=cap)
        repositories = {e.repository_id for e in items if e.repository_id is not None}
        if strength >= min_strength or len(repositories) >= 2:
            detected.append(DetectedInterest(slug, strength, tuple(items)))
    return sorted(detected, key=lambda d: (-d.strength, d.slug))
