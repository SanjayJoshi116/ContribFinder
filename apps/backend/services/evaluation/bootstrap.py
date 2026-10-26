"""Paired bootstrap over developers (spec: recommendation-evaluation "Uncertainty of a
comparison"; change evaluation-confidence, design D1). Pure.

Each resample draws as many developers as there are, with replacement, and takes the mean of
the candidate's minus the baseline's value for the drawn developers. The interval is the 2.5th
and 97.5th percentile of the resampled means (nearest rank, rounded outwards). Information only:
it never changes the improvement verdict.
"""

from __future__ import annotations

import math
import random
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .metrics import PLACES

DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 20261024
LOW, HIGH = 0.025, 0.975


@dataclass(frozen=True)
class Interval:
    diff: float  # observed mean difference, candidate minus baseline
    low: float
    high: float
    not_better: float  # share of resamples whose difference is 0 or below

    @property
    def marked(self) -> bool:
        """The interval lies entirely above or entirely below 0."""
        return self.low > 0 or self.high < 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "diff": round(self.diff, PLACES),
            "low": round(self.low, PLACES),
            "high": round(self.high, PLACES),
            "not_better": round(self.not_better, PLACES),
            "marked": self.marked,
        }


def draws(
    n: int, *, resamples: int = DEFAULT_RESAMPLES, seed: int = DEFAULT_SEED
) -> list[list[int]]:
    """The developer indexes of each resample. One generator per call, so the draws depend
    only on the developer count, the resample count and the seed."""
    if n < 1:
        raise ValueError("a comparison needs at least one developer")
    if resamples < 1:
        raise ValueError("resamples must be at least 1")
    rng = random.Random(seed)  # noqa: S311 - reproducible statistics, not security
    return [rng.choices(range(n), k=n) for _ in range(resamples)]


def paired(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
    drawn: Sequence[Sequence[int]] | None = None,
) -> Interval:
    """``drawn`` reuses one ``draws(len(baseline), ...)`` across the metrics of a comparison;
    without it the call draws its own, so an interval depends only on its own inputs."""
    if len(baseline) != len(candidate):
        raise ValueError("baseline and candidate must list the same developers")
    diffs = [c - b for b, c in zip(baseline, candidate, strict=True)]
    n = len(diffs)
    if drawn is None:
        drawn = draws(n, resamples=resamples, seed=seed)
    means = sorted(sum(diffs[i] for i in indexes) / n for indexes in drawn)
    last = len(means) - 1
    return Interval(
        diff=sum(diffs) / n,
        low=means[math.floor(LOW * last)],
        high=means[math.ceil(HIGH * last)],
        not_better=bisect_right(means, 0) / len(means),
    )
