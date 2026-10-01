"""Scoring configuration contract (design D1, D10). Weights and parameters are versioned data
on ``ScoringConfig``; this module only knows their shape and validates it."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

SIGNALS = (
    "skill",
    "language",
    "interest",
    "framework",
    "activity",
    "openness",
)
ACTIVITY_KEYS = ("recently_active", "moderately_active", "low_activity")
OPENNESS_KEYS = ("contributing", "good_first_issue", "help_wanted", "issue_templates")
TECH_SOURCE_KEYS = ("dependency", "topic")
BAND_KEYS = ("strong", "good")

V1_VERSION = "v1-deterministic"
V1_WEIGHTS: dict[str, float] = {
    "skill": 0.40,
    "language": 0.20,
    "interest": 0.15,
    "framework": 0.10,
    "activity": 0.10,
    "openness": 0.05,
}
V1_PARAMS: dict[str, Any] = {
    "bands": {"strong": 0.55, "good": 0.35},
    "activity": {"recently_active": 1.0, "moderately_active": 0.6, "low_activity": 0.2},
    "openness": {
        "contributing": 0.4,
        "good_first_issue": 0.3,
        "help_wanted": 0.2,
        "issue_templates": 0.1,
    },
    "tech_sources": {"dependency": 1.0, "topic": 0.6},
}
V1_DESCRIPTION = (
    "Initial deterministic weights (SRS-2 §30). Experimental starting values, not product truth; "
    "change them only through a new version evaluated against benchmarks."
)


def _unit_map(value: Any, keys: tuple[str, ...], name: str, errors: list[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != set(keys):
        errors.append(f"{name} must have exactly the keys {', '.join(keys)}")
        return
    for key in keys:
        v = value[key]
        if not isinstance(v, int | float) or isinstance(v, bool) or not 0 <= v <= 1:
            errors.append(f"{name}.{key} must be a number between 0 and 1")


def validate(weights: Any, params: Any) -> list[str]:
    """Return the problems with a configuration; empty when it is valid."""
    errors: list[str] = []
    if not isinstance(weights, Mapping) or set(weights) != set(SIGNALS):
        errors.append(f"weights must have exactly the signals {', '.join(SIGNALS)}")
    else:
        values = list(weights.values())
        if any(not isinstance(v, int | float) or isinstance(v, bool) or v < 0 for v in values):
            errors.append("weights must be non-negative numbers")
        elif not math.isclose(sum(values), 1.0, abs_tol=1e-6):
            errors.append(f"weights must sum to 1 (got {sum(values):.4f})")
    if not isinstance(params, Mapping):
        return [*errors, "params must be an object"]
    _unit_map(params.get("bands"), BAND_KEYS, "bands", errors)
    bands = params.get("bands")
    if isinstance(bands, Mapping):
        strong, good = bands.get("strong"), bands.get("good")
        if isinstance(strong, int | float) and isinstance(good, int | float) and good >= strong:
            errors.append("bands.good must be lower than bands.strong")
    _unit_map(params.get("activity"), ACTIVITY_KEYS, "activity", errors)
    _unit_map(params.get("openness"), OPENNESS_KEYS, "openness", errors)
    _unit_map(params.get("tech_sources"), TECH_SOURCE_KEYS, "tech_sources", errors)
    return errors
