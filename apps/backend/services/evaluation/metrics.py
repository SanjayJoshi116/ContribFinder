"""Ranking metrics (spec: recommendation-evaluation "Ranking metrics"; design D4). Pure.

A ranking is a list of repository full names, best first. Judgments map full names to a grade:
0 not relevant, 1 relevant, 2 highly relevant. An unjudged result counts as not relevant.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

PRECISION_5 = "precision@5"
PRECISION_10 = "precision@10"
RECALL_10 = "recall@10"
MRR = "mrr"
NDCG_10 = "ndcg@10"
METRICS = (PRECISION_5, PRECISION_10, RECALL_10, MRR, NDCG_10)
PRIMARY = NDCG_10
TOP_K = 10
PLACES = 4

Ranking = Sequence[str]
Judgments = Mapping[str, int]


def _relevant(name: str, judgments: Judgments) -> bool:
    return judgments.get(name, 0) >= 1


def precision_at(ranking: Ranking, judgments: Judgments, k: int) -> float:
    """Relevant results in the top k divided by k, so a list shorter than k is penalized."""
    return sum(_relevant(name, judgments) for name in ranking[:k]) / k


def recall_at(ranking: Ranking, judgments: Judgments, k: int) -> float:
    total = sum(1 for grade in judgments.values() if grade >= 1)
    if total == 0:
        return 0.0
    return sum(_relevant(name, judgments) for name in ranking[:k]) / total


def reciprocal_rank(ranking: Ranking, judgments: Judgments) -> float:
    for position, name in enumerate(ranking, start=1):
        if _relevant(name, judgments):
            return 1 / position
    return 0.0


def _dcg(grades: Sequence[int]) -> float:
    return sum(
        (2.0**grade - 1) / math.log2(position + 1) for position, grade in enumerate(grades, 1)
    )


def ndcg_at(ranking: Ranking, judgments: Judgments, k: int) -> float:
    """Graded gain ``2^grade - 1``, discount ``log2(rank + 1)``. The ideal ordering uses all the
    developer's judgments, so a relevant repository missing from the ranking lowers it."""
    ideal = _dcg(sorted(judgments.values(), reverse=True)[:k])
    if ideal == 0:
        return 0.0
    return _dcg([judgments.get(name, 0) for name in ranking[:k]]) / ideal


def unjudged_at(ranking: Ranking, judgments: Judgments, k: int) -> int:
    return sum(1 for name in ranking[:k] if name not in judgments)


@dataclass(frozen=True)
class DeveloperMetrics:
    values: dict[str, float]  # metric name -> value, unrounded
    unjudged: int  # unjudged results in the top 10


def developer_metrics(ranking: Ranking, judgments: Judgments) -> DeveloperMetrics:
    return DeveloperMetrics(
        values={
            PRECISION_5: precision_at(ranking, judgments, 5),
            PRECISION_10: precision_at(ranking, judgments, TOP_K),
            RECALL_10: recall_at(ranking, judgments, TOP_K),
            MRR: reciprocal_rank(ranking, judgments),
            NDCG_10: ndcg_at(ranking, judgments, TOP_K),
        },
        unjudged=unjudged_at(ranking, judgments, TOP_K),
    )


def mean(per_developer: Sequence[DeveloperMetrics]) -> dict[str, float]:
    """Dataset-level metrics: the mean over developers, rounded for reporting and comparison."""
    if not per_developer:
        return {name: 0.0 for name in METRICS}
    return {
        name: round(sum(m.values[name] for m in per_developer) / len(per_developer), PLACES)
        for name in METRICS
    }


def rounded(values: Mapping[str, float]) -> dict[str, float]:
    return {name: round(value, PLACES) for name, value in values.items()}
