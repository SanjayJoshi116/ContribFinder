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
    """Format 2: each configuration's effective minimum score and basis next to its metrics."""
    data = {
        "format": 2,
        "dataset": reports[0].dataset,
        "top_n": reports[0].top_n,
        "configs": {
            r.config: {
                "min_score": r.min_score,
                "min_score_basis": r.min_score_basis,
                "metrics": r.metrics,
            }
            for r in reports
        },
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def entries(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """``{version: {min_score, min_score_basis, metrics}}`` from format 1 or 2."""
    if data.get("format", 1) == 1:
        return {
            version: {"min_score": data["min_score"], "min_score_basis": "score", "metrics": m}
            for version, m in data["configs"].items()
        }
    return dict(data["configs"])
