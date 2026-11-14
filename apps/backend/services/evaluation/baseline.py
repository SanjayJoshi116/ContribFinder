"""Recorded benchmark metrics of the stored configurations (spec: recommendation-evaluation
"Regression baseline"; design D6). The test suite recomputes them; ``evaluate_ranking
--write-baseline`` rewrites the file after a deliberate ranking change."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from core.reports import write_json

from . import dataset as datasets
from .runner import Report

BASELINES = datasets.DATASETS_DIR / "baselines.json"
FORMAT = 4
# Pinned so that a local .env (RECOMMENDATION_MIN_SCORE, RECOMMENDATIONS_TOP_N) cannot change
# the recorded numbers. MIN_SCORE is the default; a configuration's own min_score wins.
MIN_SCORE = 0.10
TOP_N = 50


class BaselineError(Exception):
    pass


def read(path: Path | None = None) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((path or BASELINES).read_text(encoding="utf-8"))
    return data


def write(reports: Sequence[Report], path: Path | None = None) -> None:
    """Format 4: one entry per dataset with its top N. Each evaluated configuration replaces its
    recorded entry; configurations not evaluated and other datasets keep theirs (design D3). A
    run at a different top N must cover every configuration recorded for the dataset. Raises
    ``BaselineError`` before writing anything, also for a dataset whose file
    ``<name>.json`` is not next to the baselines file, since the baseline test and the default
    rewrite look only there. The file is written whole or not at all; an OS error is a
    ``CommandError`` naming it."""
    path = path or BASELINES
    existing = read(path) if path.exists() else {}
    recorded: dict[str, dict[str, Any]] = {
        name: {"top_n": top_n(existing, name), "configs": entries(existing, name)}
        for name in dataset_names(existing)
    }
    groups: dict[str, list[Report]] = {}
    for report in reports:
        groups.setdefault(report.dataset, []).append(report)
    for name in groups:
        if not (path.parent / f"{name}.json").is_file():
            raise BaselineError(
                f"{name}: no dataset file {path.parent / f'{name}.json'}; the baseline test "
                "reads recorded datasets only from there."
            )
    for name, group in groups.items():
        sizes = {r.top_n for r in group}
        if len(sizes) != 1:
            raise BaselineError(f"{name}: reports at different top N {sorted(sizes)}.")
        size = group[0].top_n
        previous = recorded.get(name)
        configs = dict(previous["configs"]) if previous else {}
        if previous and previous["top_n"] != size:
            missing = sorted(set(configs) - {r.config for r in group})
            if missing:
                raise BaselineError(
                    f"{name} is recorded at top N {previous['top_n']}; a run at top N "
                    f"{size} must cover every recorded configuration, missing: "
                    f"{', '.join(missing)}."
                )
        for report in group:
            configs[report.config] = {
                "min_score": report.min_score,
                "min_score_basis": report.min_score_basis,
                "metrics": report.metrics,
            }
        recorded[name] = {"top_n": size, "configs": dict(sorted(configs.items()))}
    data = {"format": FORMAT, "datasets": dict(sorted(recorded.items()))}
    write_json(path, data, what="Baseline")


def default_datasets(path: Path | None = None, datasets_dir: Path | None = None) -> list[Path]:
    """What ``--write-baseline`` rewrites without ``--dataset`` (design D1): ``benchmark-v1``,
    every recorded dataset whose file exists, and the selection dataset, without duplicates.
    The same set the baseline test checks, plus the selection benchmark."""
    path = path or BASELINES
    datasets_dir = datasets_dir or datasets.DATASETS_DIR
    existing = read(path) if path.exists() else {}
    others = [datasets_dir / f"{name}.json" for name in dataset_names(existing)]
    real = datasets_dir / datasets.REAL_BENCHMARK.name
    if datasets.selection_dataset(real) == real:  # otherwise the selection is benchmark-v1
        others.append(real)
    seed = datasets_dir / datasets.DEFAULT_DATASET.name  # always kept: a missing seed must fail
    return list(dict.fromkeys([seed, *(p for p in others if p.exists())]))


def dataset_names(data: dict[str, Any]) -> list[str]:
    if not data:
        return []
    if data.get("format", 1) < 3:
        return [data["dataset"]]
    return list(data["datasets"])


def top_n(data: dict[str, Any], dataset: str = "benchmark-v1") -> int:
    """The top N one dataset's metrics were computed at. Formats 1-3 have one for the file."""
    if data.get("format", 1) >= 4:
        return int(data["datasets"][dataset]["top_n"])
    return int(data.get("top_n", TOP_N))


def entries(data: dict[str, Any], dataset: str = "benchmark-v1") -> dict[str, dict[str, Any]]:
    """``{version: {min_score, min_score_basis, metrics}}`` for one dataset, from formats 1-4."""
    version = data.get("format", 1)
    if version == 1:
        return {
            config: {"min_score": data["min_score"], "min_score_basis": "score", "metrics": m}
            for config, m in data["configs"].items()
        }
    if version == 2:
        return dict(data["configs"])
    return dict(data["datasets"][dataset]["configs"])
