"""Seed benchmark and regression baseline (Phase 8b, group 6).

A failure in ``test_baseline_metrics_unchanged`` means the ranking moved on ``benchmark-v1``.
If the change is intended, run ``npm run manage -- evaluate_ranking --write-baseline`` and
commit the updated ``evaluation/baselines.json`` with it.
"""

import pytest

from services.evaluation import baseline
from services.evaluation.dataset import DEFAULT_DATASET, load
from services.evaluation.runner import evaluate, stored_config


def test_seed_benchmark_loads() -> None:
    dataset = load(DEFAULT_DATASET)
    assert dataset.name == "benchmark-v1"
    assert len(dataset.developers) >= 5 and dataset.repository_count >= 30
    assert any(d.features.experience_level == "beginner" for d in dataset.developers)
    assert all(any(g >= 1 for g in d.judgments.values()) for d in dataset.developers)
    assert all(name.startswith("bench/") for d in dataset.developers for name in d.judgments)


@pytest.mark.django_db
def test_baseline_metrics_unchanged() -> None:
    recorded = baseline.read()
    dataset = load(DEFAULT_DATASET)
    assert recorded["dataset"] == dataset.name
    assert set(recorded["configs"]) >= {"v1-deterministic", "v2-deterministic"}
    mismatches = []
    for version, expected in recorded["configs"].items():
        report = evaluate(
            dataset,
            stored_config(version),
            min_score=recorded["min_score"],
            top_n=recorded["top_n"],
        )
        for name, value in expected.items():
            if report.metrics[name] != value:
                mismatches.append(f"{version} {name}: recorded {value}, now {report.metrics[name]}")
    assert not mismatches, "Ranking changed on benchmark-v1:\n" + "\n".join(mismatches)
