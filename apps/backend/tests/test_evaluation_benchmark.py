"""Seed benchmark and regression baseline (Phase 8b, group 6).

A failure in ``test_baseline_metrics_unchanged`` means the ranking moved on ``benchmark-v1``.
If the change is intended, run ``npm run manage -- evaluate_ranking --write-baseline`` and
commit the updated ``evaluation/baselines.json`` with it.
"""

import json

import pytest

from services.evaluation import baseline
from services.evaluation.dataset import DATASETS_DIR, DEFAULT_DATASET, load
from services.evaluation.runner import Report, evaluate, stored_config


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
                top_n=baseline.top_n(recorded, name),
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
    assert baseline.top_n(v1, "d") == baseline.TOP_N  # no top N recorded
    v3 = {"format": 3, "top_n": 20, "datasets": {"d": {"configs": v2["configs"]}}}
    assert baseline.top_n(v3, "d") == 20  # the file's top N applies to every dataset
    assert baseline.entries(v3, "d")["a"]["min_score"] == 0.1
    v4 = {"format": 4, "datasets": {"d": {"top_n": 30, "configs": v2["configs"]}}}
    assert baseline.top_n(v4, "d") == 30
    assert baseline.entries(v4, "d") == v2["configs"]
    assert baseline.dataset_names(v4) == ["d"]


def report(config: str, ndcg: float, top_n: int = 50, dataset: str = "d") -> Report:
    return Report(
        config=config,
        dataset=dataset,
        min_score=0.1,
        top_n=top_n,
        metrics={"ndcg@10": ndcg},
        developers=(),
    )


@pytest.fixture
def folder(tmp_path):
    """A baselines folder holding the dataset files ``d`` and ``e`` the reports name."""
    for name in ("d", "e"):
        (tmp_path / f"{name}.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_baseline_write_merges(folder) -> None:
    path = folder / "baselines.json"
    baseline.write([report("v1", 0.5), report("v2", 0.6), report("v1", 0.4, dataset="e")], path)
    baseline.write([report("v2", 0.7)], path)  # only v2 rewritten
    data = baseline.read(path)
    assert data["format"] == 4
    assert baseline.top_n(data, "d") == 50
    assert {k: v["metrics"] for k, v in baseline.entries(data, "d").items()} == {
        "v1": {"ndcg@10": 0.5},
        "v2": {"ndcg@10": 0.7},
    }
    assert baseline.entries(data, "e")["v1"]["metrics"] == {"ndcg@10": 0.4}


def test_baseline_write_upgrades_format_3(folder) -> None:
    path = folder / "baselines.json"
    entry = {"min_score": 0.1, "min_score_basis": "score", "metrics": {"ndcg@10": 0.5}}
    old = {"format": 3, "top_n": 50, "datasets": {"d": {"configs": {"v1": entry}}}}
    path.write_text(json.dumps(old), encoding="utf-8")
    baseline.write([report("v2", 0.6)], path)
    data = baseline.read(path)
    assert data == {
        "format": 4,
        "datasets": {
            "d": {
                "top_n": 50,
                "configs": {"v1": entry, "v2": {**entry, "metrics": {"ndcg@10": 0.6}}},
            }
        },
    }


def test_baseline_write_different_top_n(folder) -> None:
    path = folder / "baselines.json"
    baseline.write([report("v1", 0.5), report("v2", 0.6)], path)
    before = path.read_text(encoding="utf-8")
    with pytest.raises(baseline.BaselineError, match="missing: v1"):
        baseline.write([report("v2", 0.7, top_n=20), report("v1", 0.1, dataset="e")], path)
    assert path.read_text(encoding="utf-8") == before
    baseline.write([report("v1", 0.3, top_n=20), report("v2", 0.4, top_n=20)], path)
    assert baseline.top_n(baseline.read(path), "d") == 20


def test_check_source_accepts_only_the_file_next_to_the_baselines(folder, tmp_path) -> None:
    path = folder / "baselines.json"
    baseline.check_source(folder / "d.json", "d", path)
    elsewhere = tmp_path / "other" / "d.json"
    with pytest.raises(baseline.BaselineError, match="where the baseline test reads d"):
        baseline.check_source(elsewhere, "d", path)
    with pytest.raises(baseline.BaselineError):
        baseline.check_source(folder / "d.json", "judged", path)


def test_rewriting_the_committed_baselines_keeps_their_bytes(tmp_path) -> None:
    recorded = baseline.read()
    reports = [
        Report(
            config=config,
            dataset=name,
            min_score=entry["min_score"],
            min_score_basis=entry["min_score_basis"],
            top_n=baseline.top_n(recorded, name),
            metrics=entry["metrics"],
            developers=(),
        )
        for name in baseline.dataset_names(recorded)
        for config, entry in baseline.entries(recorded, name).items()
    ]
    path = tmp_path / "baselines.json"
    path.write_bytes(baseline.BASELINES.read_bytes())
    for name in baseline.dataset_names(recorded):
        (tmp_path / f"{name}.json").write_text("{}", encoding="utf-8")
    baseline.write(reports, path)
    assert path.read_bytes() == baseline.BASELINES.read_bytes()
