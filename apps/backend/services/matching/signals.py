"""Relevance signals (spec: recommendation-engine; design D4). Pure functions: each returns a
value in 0..1 and the evidence it used. A signal without supporting data is 0 with no
evidence, never a guess."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from services.profiling.interests import SYNONYM_MATCHER
from services.profiling.taxonomy import FRAMEWORK, LANGUAGE, interest_for_topic

from .features import DeveloperFeatures, RepoData
from .technologies import Tech

MAX_EVIDENCE = 5


@dataclass(frozen=True)
class Signal:
    value: float
    evidence: tuple[dict[str, Any], ...] = field(default=())


ZERO = Signal(0.0)


def signal_of(value: float, evidence: list[dict[str, Any]]) -> Signal:
    value = round(min(1.0, max(0.0, value)), 4)
    return Signal(value, tuple(evidence)) if value > 0 else ZERO


def _noisy_or(values: list[float]) -> float:
    miss = 1.0
    for v in values:
        miss *= 1.0 - min(1.0, max(0.0, v))
    return 1.0 - miss


def skill_match(techs: Mapping[str, Tech], dev: DeveloperFeatures) -> Signal:
    """Share of the repository's stack (by usage weight) the developer has shown, weighted by
    their confidence in each technology."""
    total = sum(t.weight for t in techs.values())
    if total <= 0:
        return ZERO
    # Only technologies that add to the value (a weight-0 source adds nothing) are evidence.
    matched = [(t, c) for t in techs.values() if t.weight > 0 and (c := dev.confidence(t.slug)) > 0]
    value = sum(t.weight * c for t, c in matched) / total
    matched.sort(key=lambda tc: (-tc[0].weight * tc[1], tc[0].slug))
    evidence = [
        {"slug": t.slug, "name": t.name, "confidence": round(c, 2), "sources": list(t.sources)}
        for t, c in matched[:MAX_EVIDENCE]
    ]
    return signal_of(value, evidence)


def language_match(techs: Mapping[str, Tech], dev: DeveloperFeatures) -> Signal:
    """Code share in languages the developer knows, weighted by their confidence."""
    languages = [t for t in techs.values() if t.category == LANGUAGE and t.share]
    matched = [(t, c) for t in languages if (c := dev.confidence(t.slug)) > 0]
    value = sum((t.share or 0.0) * c for t, c in matched)
    matched.sort(key=lambda tc: (-(tc[0].share or 0.0), tc[0].slug))
    evidence = [
        {"slug": t.slug, "name": t.name, "share": t.share, "confidence": round(c, 2)}
        for t, c in matched[:MAX_EVIDENCE]
    ]
    return signal_of(value, evidence)


def framework_match(techs: Mapping[str, Tech], dev: DeveloperFeatures) -> Signal:
    """Noisy-OR of the developer's confidence in the repository's frameworks: one strong
    match counts by itself. 0 when the repository has no detected framework. A framework
    found only through a source weighted 0 (``Tech.weight`` 0) does not count, as in
    ``skill_match``."""
    matched = [
        (t, dev.skills[t.slug])
        for t in techs.values()
        if t.category == FRAMEWORK and t.weight > 0 and dev.confidence(t.slug) > 0
    ]
    value = _noisy_or([s.confidence for _, s in matched])
    matched.sort(key=lambda ts: (-ts[1].confidence, ts[0].slug))
    evidence = [
        {
            "slug": t.slug,
            "name": t.name,
            "confidence": round(s.confidence, 2),
            "repo_count": s.repo_count,
        }
        for t, s in matched[:MAX_EVIDENCE]
    ]
    return signal_of(value, evidence)


def repository_interests(repo: RepoData) -> dict[str, tuple[str, str]]:
    """``{interest_slug: (via, matched text)}`` from topics first, then description phrases."""
    found: dict[str, tuple[str, str]] = {}
    for topic in repo.topics:
        if slug := interest_for_topic(topic):
            found.setdefault(slug, ("topic", topic))
    for slug, phrase in SYNONYM_MATCHER.find(repo.description).items():
        found.setdefault(slug, ("description", phrase))
    return found


def interest_match(repo: RepoData, dev: DeveloperFeatures) -> Signal:
    matched = [
        (slug, via, text, dev.interests[slug])
        for slug, (via, text) in repository_interests(repo).items()
        if slug in dev.interests and dev.interests[slug][1] > 0
    ]
    value = _noisy_or([strength for *_, (_, strength) in matched])
    matched.sort(key=lambda m: (-m[3][1], m[0]))
    evidence = [
        {"slug": slug, "name": name, "strength": round(strength, 2), "via": via, "match": text}
        for slug, via, text, (name, strength) in matched[:MAX_EVIDENCE]
    ]
    return signal_of(value, evidence)


def activity_signal(repo: RepoData, values: Mapping[str, float]) -> Signal:
    snapshot = repo.snapshot
    if snapshot is None:
        return ZERO
    evidence = {
        "label": snapshot.activity_label,
        "days_since_push": snapshot.days_since_push,
        "commits_90d": snapshot.commits_90d,
        "prs_merged_90d": snapshot.prs_merged_90d,
    }
    return signal_of(values.get(snapshot.activity_label, 0.0), [evidence])


OPENNESS_FLAGS = (
    ("contributing", "has_contributing"),
    ("good_first_issue", "has_good_first_issue_label"),
    ("help_wanted", "has_help_wanted_label"),
    ("issue_templates", "has_issue_templates"),
)


def contribution_openness(repo: RepoData, points: Mapping[str, float]) -> Signal:
    present = [key for key, attr in OPENNESS_FLAGS if getattr(repo, attr)]
    value = sum(points[key] for key in present)
    # Only affordances worth points are evidence: a 0-point flag added nothing.
    return signal_of(value, [{"flag": key} for key in present if points[key] > 0])


def compute(
    repo: RepoData, techs: Mapping[str, Tech], dev: DeveloperFeatures, params: Mapping[str, Any]
) -> dict[str, Signal]:
    """Every repository signal for one candidate, keyed like ``ScoringConfig.weights``. The
    issue signals start at 0: issue matching (``matching.issues``) fills them in for
    candidates that pass the relevance gate."""
    return {
        "skill": skill_match(techs, dev),
        "language": language_match(techs, dev),
        "interest": interest_match(repo, dev),
        "framework": framework_match(techs, dev),
        "activity": activity_signal(repo, params["activity"]),
        "openness": contribution_openness(repo, params["openness"]),
        "issue_fit": ZERO,
        "difficulty_fit": ZERO,
    }
