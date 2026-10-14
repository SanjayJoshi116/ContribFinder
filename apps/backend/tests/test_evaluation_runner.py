"""Evaluation runner and improvement rule (Phase 8b, group 4)."""

import json

import pytest

from services.evaluation.dataset import parse
from services.evaluation.metrics import METRICS
from services.evaluation.runner import (
    ConfigError,
    Report,
    active_config,
    compare,
    evaluate,
    file_config,
    stored_config,
)
from services.ranking.config import V2_PARAMS, V2_WEIGHTS

from .test_evaluation_dataset import minimal


def report(label: str, **values: float) -> Report:
    base = {name: 0.5 for name in METRICS}
    return Report(label, "d", 0.1, 50, {**base, **values}, ())


@pytest.mark.django_db
def test_evaluation_is_deterministic_and_ranks_the_match() -> None:
    dataset = parse(minimal())
    spec = stored_config("v2-deterministic")
    first = evaluate(dataset, spec, min_score=0.1, top_n=50)
    assert first == evaluate(dataset, spec, min_score=0.1, top_n=50)
    (dev,) = first.developers
    # The Go repository has no relevance signal for a Django developer: the gate drops it.
    assert dev.top == (("bench/django-kit", 2),)
    assert first.metrics["mrr"] == 1.0 and first.metrics["ndcg@10"] == 1.0
    assert first.metrics["precision@5"] == 0.2


@pytest.mark.django_db
def test_report_json_shape() -> None:
    data = evaluate(parse(minimal()), active_config(), min_score=0.1, top_n=50).as_dict()
    json.dumps(data)  # serializable
    assert data["config"] == "v2-deterministic" and data["dataset"] == "mini"
    assert set(data["metrics"]) == set(METRICS)
    (dev,) = data["developers"]
    assert dev["top10"] == [{"repository": "bench/django-kit", "judgment": 2}]
    assert dev["unjudged_top10"] == 0 and dev["ranked"] == 1


@pytest.mark.django_db
def test_unknown_version() -> None:
    with pytest.raises(ConfigError, match="Unknown scoring configuration version: v9"):
        stored_config("v9")


def test_file_config(tmp_path) -> None:
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"weights": V2_WEIGHTS, "params": V2_PARAMS}), encoding="utf-8")
    assert file_config(path).weights == V2_WEIGHTS
    path.write_text(json.dumps({"weights": {**V2_WEIGHTS, "skill": 0.9}, "params": V2_PARAMS}))
    with pytest.raises(ConfigError, match="weights must sum to 1"):
        file_config(path)
    with pytest.raises(ConfigError, match="Cannot read"):
        file_config(tmp_path / "missing.json")


def test_better_ndcg_is_an_improvement() -> None:
    (verdict,) = compare(report("base"), [report("new", **{"ndcg@10": 0.6})])
    assert verdict.improvement and verdict.failures == ()


def test_tie_is_not_an_improvement() -> None:
    (verdict,) = compare(report("base"), [report("new")])
    assert not verdict.improvement
    assert verdict.failures == ("ndcg@10 0.5000 is not higher than 0.5000",)


def test_precision_drop_beyond_tolerance() -> None:
    candidate = report("new", **{"ndcg@10": 0.6, "precision@5": 0.45})
    (verdict,) = compare(report("base"), [candidate])
    assert not verdict.improvement
    assert verdict.failures == ("precision@5 dropped by 0.0500 (tolerance 0.0100)",)


def test_drop_within_tolerance() -> None:
    candidate = report("new", **{"ndcg@10": 0.6, "precision@5": 0.495, "mrr": 0.49})
    (verdict,) = compare(report("base"), [candidate])
    assert verdict.improvement
