"""Weighted score, match label and ranking (spec: recommendation-engine; design D5). Pure."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from services.matching.features import RepoData
from services.matching.signals import Signal
from services.matching.technologies import Tech

# Signals that say the repository fits the developer. Activity and openness describe the
# repository only, so they can order relevant candidates but never make one relevant.
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


def weighted_score(signals: Mapping[str, Signal], weights: Mapping[str, float]) -> float:
    """Internal ranking value in 0..1 (never shown as a percentage)."""
    return round(sum(weights[name] * signals[name].value for name in weights), 4)


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
) -> Scored:
    value = weighted_score(signals, weights)
    return Scored(repo, techs, signals, value, match_label(value, params["bands"]))


def is_relevant(scored: Scored) -> bool:
    return any(scored.signals[name].value > 0 for name in RELEVANCE_SIGNALS)


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
