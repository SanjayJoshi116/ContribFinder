"""Recorded benchmark metrics of the stored configurations (spec: recommendation-evaluation
"Regression baseline"; design D6). The test suite recomputes them; ``evaluate_ranking
--write-baseline`` rewrites the file after a deliberate ranking change."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .dataset import DATASETS_DIR
from .runner import Report

BASELINES = DATASETS_DIR / "baselines.json"
# Pinned so that a local .env (RECOMMENDATION_MIN_SCORE, RECOMMENDATIONS_TOP_N) cannot change
# the recorded numbers. MIN_SCORE is the default; a configuration's own min_score wins.
MIN_SCORE = 0.10
TOP_N = 50


def read(path: Path = BASELINES) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def write(reports: Sequence[Report], path: Path = BASELINES) -> None:
    """Format 3: one entry per dataset. Rewrites only the evaluated dataset's entry and keeps
    the others; each configuration has its effective minimum score and basis with its metrics."""
    existing = read(path) if path.exists() else {}
    datasets = {name: {"configs": entries(existing, name)} for name in dataset_names(existing)}
    datasets[reports[0].dataset] = {
        "configs": {
            r.config: {
                "min_score": r.min_score,
                "min_score_basis": r.min_score_basis,
                "metrics": r.metrics,
            }
            for r in reports
        }
    }
    data = {"format": 3, "top_n": reports[0].top_n, "datasets": dict(sorted(datasets.items()))}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def dataset_names(data: dict[str, Any]) -> list[str]:
    if not data:
        return []
    if data.get("format", 1) < 3:
        return [data["dataset"]]
    return list(data["datasets"])


def entries(data: dict[str, Any], dataset: str = "benchmark-v1") -> dict[str, dict[str, Any]]:
    """``{version: {min_score, min_score_basis, metrics}}`` for one dataset, from formats 1-3."""
    version = data.get("format", 1)
    if version == 1:
        return {
            config: {"min_score": data["min_score"], "min_score_basis": "score", "metrics": m}
            for config, m in data["configs"].items()
        }
    if version == 2:
        return dict(data["configs"])
    return dict(data["datasets"][dataset]["configs"])
