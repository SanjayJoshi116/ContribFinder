"""Evaluate scoring configurations on a benchmark and compare them (spec:
recommendation-evaluation "Evaluation command", "Improvement rule"; design D3, D5).

Ranking goes through ``rank_pool``, the stage generation uses. Only ``stored_config`` reads
the database.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from recommendations.models import ScoringConfig
from services.matching.issues import IssueFeature
from services.ranking import config as scoring_config
from services.ranking.pipeline import rank_pool

from . import metrics
from .dataset import Dataset

DEFAULT_TOLERANCE = 0.01


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class ConfigSpec:
    label: str  # stored version, or the file path for an unsaved configuration
    weights: Mapping[str, float]
    params: Mapping[str, Any]


def _checked(label: str, weights: Any, params: Any) -> ConfigSpec:
    if errors := scoring_config.validate(weights, params, stored=True):
        raise ConfigError(f"Configuration {label} is invalid: {'; '.join(errors)}")
    return ConfigSpec(label, weights, params)


def stored_config(version: str) -> ConfigSpec:
    row = ScoringConfig.objects.filter(version=version).first()
    if row is None:
        raise ConfigError(f"Unknown scoring configuration version: {version}")
    return _checked(version, row.weights, row.params)


def active_config() -> ConfigSpec:
    row = ScoringConfig.objects.filter(is_active=True).first()
    if row is None:
        raise ConfigError("No active scoring configuration")
    return _checked(row.version, row.weights, row.params)


def file_config(path: Path | str) -> ConfigSpec:
    """An unsaved configuration: a JSON object with ``weights`` and ``params``."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"Cannot read configuration file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Configuration file {path} must hold an object")
    return _checked(str(path), raw.get("weights"), raw.get("params"))


@dataclass(frozen=True)
class DeveloperResult:
    id: str
    top: tuple[tuple[str, int | None], ...]  # top 10: full name and judgment (None = unjudged)
    ranked: int  # length of the full ranked list
    metrics: dict[str, float]  # rounded
    unjudged: int


@dataclass(frozen=True)
class Report:
    config: str
    dataset: str
    min_score: float
    top_n: int
    metrics: dict[str, float]  # dataset-level means, rounded
    developers: tuple[DeveloperResult, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "dataset": self.dataset,
            "min_score": self.min_score,
            "top_n": self.top_n,
            "metrics": self.metrics,
            "developers": [
                {
                    "id": d.id,
                    "ranked": d.ranked,
                    "metrics": d.metrics,
                    "unjudged_top10": d.unjudged,
                    "top10": [{"repository": n, "judgment": g} for n, g in d.top],
                }
                for d in self.developers
            ],
        }


def _issues_from(
    issues: Mapping[int, list[IssueFeature]],
) -> Callable[[Sequence[int]], dict[int, list[IssueFeature]]]:
    return lambda ids: {i: issues[i] for i in ids if i in issues}


def evaluate(dataset: Dataset, spec: ConfigSpec, *, min_score: float, top_n: int) -> Report:
    results = []
    per_developer = []
    for dev in dataset.developers:
        ranked = rank_pool(
            dev.features,
            dev.candidates,
            spec.weights,
            spec.params,
            _issues_from(dev.issues),
            min_score=min_score,
            top_n=top_n,
        )
        names = [s.repo.full_name for s in ranked]
        found = metrics.developer_metrics(names, dev.judgments)
        per_developer.append(found)
        results.append(
            DeveloperResult(
                id=dev.id,
                top=tuple((n, dev.judgments.get(n)) for n in names[: metrics.TOP_K]),
                ranked=len(names),
                metrics=metrics.rounded(found.values),
                unjudged=found.unjudged,
            )
        )
    return Report(
        config=spec.label,
        dataset=dataset.name,
        min_score=min_score,
        top_n=top_n,
        metrics=metrics.mean(per_developer),
        developers=tuple(results),
    )


@dataclass(frozen=True)
class Verdict:
    config: str
    improvement: bool
    failures: tuple[str, ...]  # why it is not an improvement


def compare(
    baseline: Report, candidates: Sequence[Report], tolerance: float = DEFAULT_TOLERANCE
) -> list[Verdict]:
    """A candidate improves on the baseline only with a strictly higher primary metric
    (NDCG@10) and no other metric lower by more than ``tolerance``."""
    verdicts = []
    for report in candidates:
        failures = []
        if report.metrics[metrics.PRIMARY] <= baseline.metrics[metrics.PRIMARY]:
            failures.append(
                f"{metrics.PRIMARY} {report.metrics[metrics.PRIMARY]:.4f} is not higher than "
                f"{baseline.metrics[metrics.PRIMARY]:.4f}"
            )
        for name in metrics.METRICS:
            if name == metrics.PRIMARY:
                continue
            drop = round(baseline.metrics[name] - report.metrics[name], metrics.PLACES)
            if drop > tolerance:
                failures.append(f"{name} dropped by {drop:.4f} (tolerance {tolerance:.4f})")
        verdicts.append(Verdict(report.config, not failures, tuple(failures)))
    return verdicts
