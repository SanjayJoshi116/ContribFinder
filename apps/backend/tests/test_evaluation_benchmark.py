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
    names = baseline.dataset_names(recorded)
    assert "benchmark-v1" in names
    mismatches = []
    for name in names:
        path = DATASETS_DIR / f"{name}.json"
        if not path.exists():  # e.g. benchmark-v2 kept local, not committed
            continue
        dataset = load(path)
        entries = baseline.entries(recorded, name)
        assert {"v1-deterministic", "v2-deterministic"} <= set(entries)
        for version, entry in entries.items():
            report = evaluate(
                dataset,
                stored_config(version),
                min_score=baseline.MIN_SCORE,
                top_n=recorded["top_n"],
            )
            if (report.min_score, report.min_score_basis) != (
                entry["min_score"],
                entry["min_score_basis"],
            ):
                mismatches.append(f"{name} {version} min score: recorded {entry['min_score']}")
            for metric, value in entry["metrics"].items():
                if report.metrics[metric] != value:
                    mismatches.append(
                        f"{name} {version} {metric}: recorded {value}, now {report.metrics[metric]}"
                    )
    assert not mismatches, "Ranking changed:" + "".join(f"\n  {m}" for m in mismatches)


def test_baseline_formats(tmp_path) -> None:
    metrics = {"ndcg@10": 0.5}
    v1 = {"format": 1, "dataset": "d", "min_score": 0.1, "configs": {"a": metrics}}
    v2 = {"format": 2, "dataset": "d", "configs": {"a": {"min_score": 0.1, "metrics": metrics}}}
    assert baseline.entries(v1, "d")["a"]["metrics"] == metrics
    assert baseline.entries(v2, "d")["a"]["min_score"] == 0.1
    assert baseline.dataset_names(v1) == ["d"]
