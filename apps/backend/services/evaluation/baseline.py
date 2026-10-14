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
# the recorded numbers.
MIN_SCORE = 0.10
TOP_N = 50


def read(path: Path = BASELINES) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def write(reports: Sequence[Report], path: Path = BASELINES) -> None:
    first = reports[0]
    data = {
        "dataset": first.dataset,
        "min_score": first.min_score,
        "top_n": first.top_n,
        "configs": {r.config: r.metrics for r in reports},
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
