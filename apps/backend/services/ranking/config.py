"""Scoring configuration contract (design D1, D10). Weights and parameters are versioned data
on ``ScoringConfig``; this module only knows their shape and validates it."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, TypeGuard

SIGNALS = (
    "skill",
    "language",
    "interest",
    "framework",
    "activity",
    "openness",
    "issue_fit",
    "difficulty_fit",
)
ISSUE_SIGNALS = ("issue_fit", "difficulty_fit")
# Configurations stored before Phase 7 (v1) have no issue signals and no ``params.issues``.
LEGACY_SIGNALS = tuple(s for s in SIGNALS if s not in ISSUE_SIGNALS)
ACTIVITY_KEYS = ("recently_active", "moderately_active", "low_activity")
OPENNESS_KEYS = ("contributing", "good_first_issue", "help_wanted", "issue_templates")
TECH_SOURCE_KEYS = ("dependency", "topic")
BAND_KEYS = ("strong", "good")
ISSUE_WEIGHT_KEYS = ("technology", "difficulty", "approachability")
APPROACHABILITY_KEYS = ("good_first_issue", "help_wanted")
EXPERIENCE_LEVELS = ("beginner", "intermediate", "experienced", "unknown")
DIFFICULTIES = ("beginner", "intermediate", "advanced", "unknown")
# Optional (absent = v2 behavior): ``issues.difficulty_fit_mode`` and ``relevance_scaling``.
DIFFICULTY_FIT_BEST = "best"
DIFFICULTY_FIT_WEIGHTED = "weighted"
DIFFICULTY_FIT_MODES = (DIFFICULTY_FIT_BEST, DIFFICULTY_FIT_WEIGHTED)
# Optional: ``min_score`` (0..1) and ``min_score_basis``; absent = the installation setting.
MIN_SCORE_BASES = ("score", "relevance")

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


V2_VERSION = "v2-deterministic"
V2_WEIGHTS: dict[str, float] = {
    "skill": 0.35,
    "language": 0.15,
    "interest": 0.15,
    "framework": 0.10,
    "activity": 0.10,
    "openness": 0.05,
    "issue_fit": 0.05,
    "difficulty_fit": 0.05,
}
V2_ISSUE_PARAMS: dict[str, Any] = {
    "weights": {"technology": 0.6, "difficulty": 0.25, "approachability": 0.15},
    "min_score": 0.3,
    "per_recommendation": 5,
    "saturation": 3.0,
    # Approachability of an issue: its best label's value.
    "approachability": {"good_first_issue": 1.0, "help_wanted": 0.6},
    # Rows: the developer's experience level; columns: the issue's estimated difficulty.
    "difficulty_fit": {
        "beginner": {"beginner": 1.0, "intermediate": 0.5, "advanced": 0.0, "unknown": 0.3},
        "intermediate": {"beginner": 0.7, "intermediate": 1.0, "advanced": 0.5, "unknown": 0.4},
        "experienced": {"beginner": 0.4, "intermediate": 0.8, "advanced": 1.0, "unknown": 0.5},
        "unknown": {"beginner": 0.8, "intermediate": 0.7, "advanced": 0.4, "unknown": 0.4},
    },
}
V2_PARAMS: dict[str, Any] = {**V1_PARAMS, "issues": V2_ISSUE_PARAMS}
V2_DESCRIPTION = (
    "v1 plus issue fit and difficulty fit (Phase 7). Experimental starting values, not product "
    "truth; change them only through a new version evaluated against benchmarks."
)


def _is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _unit_map(value: Any, keys: tuple[str, ...], name: str, errors: list[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != set(keys):
        errors.append(f"{name} must have exactly the keys {', '.join(keys)}")
        return
    for key in keys:
        v = value[key]
        if not _is_number(v) or not 0 <= v <= 1:
            errors.append(f"{name}.{key} must be a number between 0 and 1")


def _issue_params(value: Any, errors: list[str]) -> None:
    if not isinstance(value, Mapping):
        errors.append("issues must be an object")
        return
    weights = value.get("weights")
    _unit_map(weights, ISSUE_WEIGHT_KEYS, "issues.weights", errors)
    if (
        isinstance(weights, Mapping)
        and all(_is_number(weights.get(k)) for k in ISSUE_WEIGHT_KEYS)
        and not math.isclose(sum(weights[k] for k in ISSUE_WEIGHT_KEYS), 1.0, abs_tol=1e-6)
    ):
        errors.append("issues.weights must sum to 1")
    min_score = value.get("min_score")
    if not _is_number(min_score) or not 0 <= min_score <= 1:
        errors.append("issues.min_score must be a number between 0 and 1")
    per = value.get("per_recommendation")
    if not isinstance(per, int) or isinstance(per, bool) or per < 1:
        errors.append("issues.per_recommendation must be an integer of at least 1")
    saturation = value.get("saturation")
    if not _is_number(saturation) or saturation <= 0:
        errors.append("issues.saturation must be a number above 0")
    _unit_map(value.get("approachability"), APPROACHABILITY_KEYS, "issues.approachability", errors)
    if "difficulty_fit_mode" in value and value["difficulty_fit_mode"] not in DIFFICULTY_FIT_MODES:
        errors.append(
            f"issues.difficulty_fit_mode must be one of {', '.join(DIFFICULTY_FIT_MODES)}"
        )
    table = value.get("difficulty_fit")
    if not isinstance(table, Mapping) or set(table) != set(EXPERIENCE_LEVELS):
        errors.append(
            f"issues.difficulty_fit must have exactly the rows {', '.join(EXPERIENCE_LEVELS)}"
        )
        return
    for level in EXPERIENCE_LEVELS:
        _unit_map(table[level], DIFFICULTIES, f"issues.difficulty_fit.{level}", errors)


def validate(weights: Any, params: Any, *, stored: bool = False) -> list[str]:
    """Return the problems with a configuration; empty when it is valid.

    ``stored`` accepts a configuration saved before the issue signals existed (v1): no issue
    weights and no ``params.issues``. Scoring treats its missing weights as 0."""
    errors: list[str] = []
    legacy = stored and isinstance(weights, Mapping) and set(weights) == set(LEGACY_SIGNALS)
    if not isinstance(weights, Mapping) or not (legacy or set(weights) == set(SIGNALS)):
        errors.append(f"weights must have exactly the signals {', '.join(SIGNALS)}")
    else:
        values = list(weights.values())
        if any(not _is_number(v) or v < 0 for v in values):
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
    if not legacy or "issues" in params:
        _issue_params(params.get("issues"), errors)
    if "relevance_scaling" in params and not isinstance(params["relevance_scaling"], bool):
        errors.append("relevance_scaling must be true or false")
    if "min_score" in params:
        value = params["min_score"]
        if not _is_number(value) or not 0 <= value <= 1:
            errors.append("min_score must be a number between 0 and 1")
    if "min_score_basis" in params:
        if "min_score" not in params:
            errors.append("min_score_basis requires min_score")
        elif params["min_score_basis"] not in MIN_SCORE_BASES:
            errors.append(f"min_score_basis must be one of {', '.join(MIN_SCORE_BASES)}")
    return errors
