"""Weighted score, match label and ranking (spec: recommendation-engine; design D5). Pure."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from services.matching.features import RepoData
from services.matching.issues import NO_MATCH, IssueMatch
from services.matching.signals import Signal
from services.matching.technologies import Tech

# Signals that say the repository fits the developer. Activity, openness and the issue signals
# describe what the repository offers, so they can order relevant candidates but never make
# one relevant.
RELEVANCE_SIGNALS = ("skill", "language", "framework", "interest")

STRONG = "strong"
GOOD = "good"
PARTIAL = "partial"


@dataclass(frozen=True)
class Scored:
    repo: RepoData
    techs: Mapping[str, Tech]
    signals: Mapping[str, Signal]
    score: float
    label: str
    issues: IssueMatch = NO_MATCH


def weighted_score(signals: Mapping[str, Signal], weights: Mapping[str, float]) -> float:
    """Internal ranking value in 0..1 (never shown as a percentage). A signal the
    configuration has no weight for (issue signals under v1) counts as 0."""
    return round(sum(weights.get(name, 0.0) * signal.value for name, signal in signals.items()), 4)


def match_label(score: float, bands: Mapping[str, float]) -> str:
    if score >= bands["strong"]:
        return STRONG
    if score >= bands["good"]:
        return GOOD
    return PARTIAL


def score_candidate(
    repo: RepoData,
    techs: Mapping[str, Tech],
    signals: Mapping[str, Signal],
    weights: Mapping[str, float],
    params: Mapping[str, Any],
    issues: IssueMatch = NO_MATCH,
) -> Scored:
    value = weighted_score(signals, weights)
    return Scored(repo, techs, signals, value, match_label(value, params["bands"]), issues)


def has_relevance(signals: Mapping[str, Signal]) -> bool:
    return any(signals[name].value > 0 for name in RELEVANCE_SIGNALS)


def is_relevant(scored: Scored) -> bool:
    return has_relevance(scored.signals)


def rank(scored: Iterable[Scored], *, min_score: float, top_n: int) -> list[Scored]:
    """Best first: score, then best search rank (unranked last), then name. Keeps the top N
    that are relevant (a relevance signal above 0) and score at least ``min_score``."""
    kept = [s for s in scored if s.score >= min_score and is_relevant(s)]
    kept.sort(
        key=lambda s: (
            -s.score,
            s.repo.best_search_rank if s.repo.best_search_rank is not None else math.inf,
            s.repo.full_name.lower(),
        )
    )
    return kept[:top_n]
