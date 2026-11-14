"""Weighted score, match label and ranking (spec: recommendation-engine; design D5). Pure."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from services.matching.features import RepoData
from services.matching.issues import NO_MATCH, IssueMatch
from services.matching.signals import Signal
from services.matching.technologies import Tech

from .config import MIN_SCORE_BASES

# Signals that say the repository fits the developer. Activity, openness and the issue signals
# describe what the repository offers, so they can order relevant candidates but never make
# one relevant.
RELEVANCE_SIGNALS = ("skill", "language", "framework", "interest")
# What the repository offers. With ``params.relevance_scaling`` their contributions are scaled by
# the candidate's relevance strength, so they order relevant candidates without lifting a weak
# match past a strong one.
OFFER_SIGNALS = ("activity", "openness", "issue_fit", "difficulty_fit")

# What a minimum score is compared with (``params.min_score_basis``; absent = score).
BASIS_SCORE, BASIS_RELEVANCE = MIN_SCORE_BASES

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
    relevance: float = 0.0  # the relevance signals' part of ``score``; never scaled
    relevant: bool = False  # passes the relevance gate (``has_relevance``)
    # Each signal's contribution (``contributions``), unrounded: ``score`` is their rounded
    # sum, and reasons are built from them.
    parts: Mapping[str, float] = field(default_factory=dict)


def contributions(
    signals: Mapping[str, Signal], weights: Mapping[str, float], params: Mapping[str, Any]
) -> dict[str, float]:
    """Each signal's contribution to the score. A signal the configuration has no weight for
    (issue signals under v1) contributes 0. With relevance scaling, offer signals are multiplied
    by the relevance strength: the weighted mean of the relevance signals."""
    plain = {name: weights.get(name, 0.0) * signal.value for name, signal in signals.items()}
    if not params.get("relevance_scaling"):
        return plain
    relevance_weight = sum(weights.get(name, 0.0) for name in RELEVANCE_SIGNALS)
    strength = (
        sum(plain.get(name, 0.0) for name in RELEVANCE_SIGNALS) / relevance_weight
        if relevance_weight
        else 0.0
    )
    return {
        name: value * strength if name in OFFER_SIGNALS else value for name, value in plain.items()
    }


def _total(parts: Mapping[str, float]) -> float:
    return round(sum(parts.values()), 4)


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
    parts = contributions(signals, weights, params)
    value = _total(parts)  # internal ranking value in 0..1, never shown as a percentage
    relevance = _total({name: parts.get(name, 0.0) for name in RELEVANCE_SIGNALS})
    return Scored(
        repo,
        techs,
        signals,
        value,
        match_label(value, params["bands"]),
        issues,
        relevance,
        has_relevance(signals, weights),
        parts,
    )


def has_relevance(signals: Mapping[str, Signal], weights: Mapping[str, float]) -> bool:
    """The relevance gate: some relevance signal contributes to the score (value and weight
    above 0). Tested on the unrounded inputs, not on ``Scored.relevance``, which is rounded and
    would drop a tiny contribution. Relevance scaling never scales these contributions."""
    return any(weights.get(name, 0.0) > 0 and signals[name].value > 0 for name in RELEVANCE_SIGNALS)


def rank(
    scored: Iterable[Scored], *, min_score: float, top_n: int | None, basis: str = BASIS_SCORE
) -> list[Scored]:
    """Best first: score, then best search rank (unranked last), then name. Keeps the top N
    (all with ``top_n`` None) that are relevant (``has_relevance``) and reach
    ``min_score``: with ``basis`` ``relevance``, only the relevance part of the score is
    compared."""
    kept = [
        s
        for s in scored
        if (s.relevance if basis == BASIS_RELEVANCE else s.score) >= min_score and s.relevant
    ]
    kept.sort(
        key=lambda s: (
            -s.score,
            s.repo.best_search_rank if s.repo.best_search_rank is not None else math.inf,
            s.repo.full_name.lower(),
        )
    )
    return kept[:top_n]
