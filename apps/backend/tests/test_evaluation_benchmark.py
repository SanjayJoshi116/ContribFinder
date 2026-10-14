"""Seed benchmark and regression baseline (Phase 8b, group 6).

A failure in ``test_baseline_metrics_unchanged`` means the ranking moved on ``benchmark-v1``.
If the change is intended, run ``npm run manage -- evaluate_ranking --write-baseline`` and
commit the updated ``evaluation/baselines.json`` with it.
"""

import pytest

from services.evaluation import baseline
from services.evaluation.dataset import DATASETS_DIR, DEFAULT_DATASET, load
from services.evaluation.runner import evaluate, stored_config


def test_seed_benchmark_loads() -> None:
    dataset = load(DEFAULT_DATASET)
    assert dataset.name == "benchmark-v1"
    assert len(dataset.developers) >= 5 and dataset.repository_count >= 30
    assert any(d.features.experience_level == "beginner" for d in dataset.developers)
    assert all(any(g >= 1 for g in d.judgments.values()) for d in dataset.developers)
    assert all(name.startswith("bench/") for d in dataset.developers for name in d.judgments)


def test_holdout_loads() -> None:
    holdout = load(DATASETS_DIR / "holdout-v1.json")
    assert holdout.name == "holdout-v1" and len(holdout.developers) >= 4
    assert any(d.features.experience_level == "beginner" for d in holdout.developers)
    benchmark_ids = {d.id for d in load(DEFAULT_DATASET).developers}
    assert not benchmark_ids & {d.id for d in holdout.developers}


def test_fresh_holdout_loads() -> None:
    holdout = load(DATASETS_DIR / "holdout-v2.json")
    assert holdout.name == "holdout-v2" and len(holdout.developers) >= 4
    assert any(d.features.experience_level == "beginner" for d in holdout.developers)
    earlier = {
        d.id
        for path in (DEFAULT_DATASET, DATASETS_DIR / "holdout-v1.json")
        for d in load(path).developers
    }
    assert not earlier & {d.id for d in holdout.developers}


@pytest.mark.django_db
def test_baseline_metrics_unchanged() -> None:
    recorded = baseline.read()
    entries = baseline.entries(recorded)
    dataset = load(DEFAULT_DATASET)
    assert recorded["dataset"] == dataset.name
    assert set(entries) >= {"v1-deterministic", "v2-deterministic"}
    mismatches = []
    for version, entry in entries.items():
        report = evaluate(
            dataset, stored_config(version), min_score=baseline.MIN_SCORE, top_n=recorded["top_n"]
        )
        if (report.min_score, report.min_score_basis) != (
            entry["min_score"],
            entry["min_score_basis"],
        ):
            mismatches.append(f"{version} min score: recorded {entry['min_score']}")
        for name, value in entry["metrics"].items():
            if report.metrics[name] != value:
                mismatches.append(f"{version} {name}: recorded {value}, now {report.metrics[name]}")
    assert not mismatches, "Ranking changed on benchmark-v1:\n" + "\n".join(mismatches)
