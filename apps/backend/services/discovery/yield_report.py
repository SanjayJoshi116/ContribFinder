"""How discovery's search requests were spent, per strategy and star band (spec:
repository-discovery "Discovery yield report"; change discovery-search-yield, design D3).

``load`` is the one query; ``build`` is pure. Reads only each finished run's ``query_yield``
(written by the search step) and its first finished query key, to tell runs without a search
apart: never query text, users, jobs or repositories, so the report holds
aggregates only.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, NamedTuple

from django.db.models.functions import Coalesce

from jobs.models import SyncJob
from services.evaluation.metrics import PLACES

from .queries import SOURCE_BY_STRATEGY

ALL_BANDS = "all"  # the band of a query planned with a single configured band
STRATEGY_ORDER = tuple(str(source) for source in SOURCE_BY_STRATEGY.values())

QueryYield = Mapping[str, Any]


@dataclass
class _Tally:
    requests: int = 0
    refused: int = 0
    results: int = 0
    rejections: Counter[str] = field(default_factory=Counter)
    recorded: int = 0

    def add(self, found: QueryYield) -> None:
        self.requests += 1
        if found.get("refused"):
            self.refused += 1
            return
        self.results += int(found.get("results", 0))
        self.rejections.update({k: int(v) for k, v in (found.get("rejections") or {}).items()})
        self.recorded += int(found.get("recorded", 0))


@dataclass(frozen=True)
class YieldRow:
    name: str  # strategy, band, "<strategy> <band>" or "total"
    requests: int
    refused: int
    results: int
    rejections: dict[str, int]  # most frequent first
    recorded: int

    @property
    def results_per_request(self) -> float | None:
        ran = self.requests - self.refused
        return self.results / ran if ran else None

    @property
    def recorded_share(self) -> float | None:
        return self.recorded / self.results if self.results else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "requests": self.requests,
            "refused": self.refused,
            "results": self.results,
            "rejections": self.rejections,
            "recorded": self.recorded,
            "results_per_request": _rounded(self.results_per_request),
            "recorded_share": _rounded(self.recorded_share),
        }


@dataclass(frozen=True)
class YieldReport:
    runs: int  # finished runs in the window
    runs_without_search: int  # planned nothing or ended before searching; in no figure
    runs_without_yield: int  # searched before query yield was recorded; in no figure
    total: YieldRow
    strategies: tuple[YieldRow, ...]
    bands: tuple[YieldRow, ...]
    strategy_bands: tuple[YieldRow, ...]
    since_days: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "since_days": self.since_days,
            "runs": self.runs,
            "runs_without_search": self.runs_without_search,
            "runs_without_yield": self.runs_without_yield,
            "total": self.total.as_dict(),
            "strategies": [row.as_dict() for row in self.strategies],
            "bands": [row.as_dict() for row in self.bands],
            "strategy_bands": [row.as_dict() for row in self.strategy_bands],
        }


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, PLACES)


def _row(name: str, tally: _Tally) -> YieldRow:
    rejections = dict(sorted(tally.rejections.items(), key=lambda item: (-item[1], item[0])))
    return YieldRow(name, tally.requests, tally.refused, tally.results, rejections, tally.recorded)


def _strategy_key(source: str) -> tuple[int, str]:
    return (
        STRATEGY_ORDER.index(source) if source in STRATEGY_ORDER else len(STRATEGY_ORDER),
        source,
    )


def _band_key(band: str) -> tuple[int, str]:
    """Bands by their lower star bound (``20..999`` before ``1000+``); ``all`` last."""
    low = re.match(r"\d+", band)
    return (int(low.group()) if low else 10**12, band)


class Run(NamedTuple):
    """What the report reads of one finished run: its query yield and the first query it
    finished (done, or refused by GitHub), None when no query finished."""

    query_yield: Mapping[str, QueryYield] | None
    first_finished: str | None

    @property
    def searched(self) -> bool:
        # A run that planned nothing, or ended before its first query finished, made no search;
        # one that finished queries without a yield ran before the yield was recorded (CR5-4).
        return bool(self.query_yield) or self.first_finished is not None


def load(since: datetime | None) -> list[Run]:
    """Every finished discovery run in the window (by start, or creation for a run that never
    started). One query, reading three JSON keys (never the rest of the metadata); active runs
    are left out."""
    jobs = SyncJob.objects.filter(
        job_type=SyncJob.JobType.REPOSITORY_DISCOVERY, status__in=SyncJob.TERMINAL_STATUSES
    ).order_by()
    if since is not None:
        jobs = jobs.alias(window=Coalesce("started_at", "created_at")).filter(window__gte=since)
    rows = jobs.values_list(
        "metadata__query_yield", "metadata__queries_done__0", "metadata__queries_skipped__0"
    )
    return [Run(found, done if done is not None else refused) for found, done, refused in rows]


def build(runs: Iterable[Run], *, since_days: int | None = None) -> YieldReport:
    total = _Tally()
    by_strategy: dict[str, _Tally] = {}
    by_band: dict[str, _Tally] = {}
    by_both: dict[tuple[str, str], _Tally] = {}
    count = without_search = without = 0
    for run in runs:
        count += 1
        if not run.searched:
            without_search += 1
            continue
        if not run.query_yield:
            without += 1
            continue
        for found in run.query_yield.values():
            source = str(found.get("source", ""))
            band = str(found.get("band") or ALL_BANDS)
            for tally in (
                total,
                by_strategy.setdefault(source, _Tally()),
                by_band.setdefault(band, _Tally()),
                by_both.setdefault((source, band), _Tally()),
            ):
                tally.add(found)
    return YieldReport(
        runs=count,
        runs_without_search=without_search,
        runs_without_yield=without,
        total=_row("total", total),
        strategies=tuple(_row(s, by_strategy[s]) for s in sorted(by_strategy, key=_strategy_key)),
        bands=tuple(_row(b, by_band[b]) for b in sorted(by_band, key=_band_key)),
        strategy_bands=tuple(
            _row(f"{s} {b}", by_both[(s, b)])
            for s, b in sorted(by_both, key=lambda k: (_strategy_key(k[0]), _band_key(k[1])))
        ),
        since_days=since_days,
    )
