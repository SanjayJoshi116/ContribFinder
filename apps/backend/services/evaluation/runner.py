"""Evaluate scoring configurations on a benchmark and compare them (spec:
recommendation-evaluation "Evaluation command", "Improvement rule", "Uncertainty of a
comparison"; design D3, D5; change evaluation-confidence).

Ranking goes through ``rank_pool``, the stage generation uses. Only ``stored_config`` reads
the database.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from recommendations.models import ScoringConfig
from services.matching.issues import IssueFeature
from services.ranking import config as scoring_config
from services.ranking.pipeline import rank_pool

from . import bootstrap, metrics
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
    unjudged: int
    values: dict[str, float]  # unrounded, for the bootstrap

    @property
    def metrics(self) -> dict[str, float]:
        """Rounded, as reported."""
        return metrics.rounded(self.values)


@dataclass(frozen=True)
class Report:
    config: str
    dataset: str
    min_score: float  # effective: the configuration's own unless overridden
    top_n: int
    metrics: dict[str, float]  # dataset-level means, rounded
    developers: tuple[DeveloperResult, ...]
    min_score_basis: str = "score"
    min_score_overridden: bool = False
    # Means per developer kind (persona, real); only when the dataset holds both kinds.
    subsets: dict[str, dict[str, float]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "dataset": self.dataset,
            "min_score": self.min_score,
            "min_score_basis": self.min_score_basis,
            "min_score_overridden": self.min_score_overridden,
            "subsets": self.subsets,
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


def evaluate(
    dataset: Dataset,
    spec: ConfigSpec,
    *,
    min_score: float,
    top_n: int,
    override: bool = False,
) -> Report:
    """Rank and score every developer. ``min_score`` is the default, as in generation: a
    configuration's own ``min_score`` wins, unless ``override`` forces ``min_score`` on it."""
    params = {**spec.params, "min_score": min_score} if override else spec.params
    effective = params.get("min_score", min_score)
    results = []
    per_developer = []
    by_kind: dict[str, list[metrics.DeveloperMetrics]] = {}
    for dev in dataset.developers:
        ranked = rank_pool(
            dev.features,
            dev.candidates,
            spec.weights,
            params,
            _issues_from(dev.issues),
            min_score=min_score,
            top_n=top_n,
        )
        names = [s.repo.full_name for s in ranked]
        found = metrics.developer_metrics(names, dev.judgments)
        per_developer.append(found)
        by_kind.setdefault(dev.kind, []).append(found)
        results.append(
            DeveloperResult(
                id=dev.id,
                top=tuple((n, dev.judgments.get(n)) for n in names[: metrics.TOP_K]),
                ranked=len(names),
                unjudged=found.unjudged,
                values=dict(found.values),
            )
        )
    return Report(
        config=spec.label,
        dataset=dataset.name,
        min_score=effective,
        top_n=top_n,
        metrics=metrics.mean(per_developer),
        developers=tuple(results),
        min_score_basis=params.get("min_score_basis", "score"),
        min_score_overridden=override,
        subsets=(
            {kind: metrics.mean(found) for kind, found in sorted(by_kind.items())}
            if len(by_kind) > 1
            else {}
        ),
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


def uncertainty(
    baseline: Report,
    candidate: Report,
    *,
    resamples: int = bootstrap.DEFAULT_RESAMPLES,
    seed: int = bootstrap.DEFAULT_SEED,
) -> dict[str, bootstrap.Interval]:
    """Per metric, the paired bootstrap interval of the candidate's difference from the
    baseline over the same developers. Information only: ``compare`` alone decides."""
    if [d.id for d in baseline.developers] != [d.id for d in candidate.developers]:
        raise ValueError(f"{baseline.config} and {candidate.config} rank different developers")
    # Every metric resamples the same developers: draw once.
    drawn = bootstrap.draws(len(baseline.developers), resamples=resamples, seed=seed)
    return {
        name: bootstrap.paired(
            [d.values[name] for d in baseline.developers],
            [d.values[name] for d in candidate.developers],
            drawn=drawn,
        )
        for name in metrics.METRICS
    }
