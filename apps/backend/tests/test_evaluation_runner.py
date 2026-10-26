"""Evaluation runner and improvement rule (Phase 8b, group 4)."""

import copy
import json

import pytest

from services.evaluation.dataset import DEFAULT_DATASET, load, parse
from services.evaluation.metrics import METRICS
from services.evaluation.runner import (
    ConfigError,
    ConfigSpec,
    DeveloperResult,
    Report,
    active_config,
    compare,
    evaluate,
    file_config,
    stored_config,
    uncertainty,
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


def test_configuration_minimum_and_override() -> None:
    dataset = parse(minimal())
    strict = ConfigSpec("strict", V2_WEIGHTS, {**V2_PARAMS, "min_score": 0.99})
    own = evaluate(dataset, strict, min_score=0.1, top_n=50)
    assert own.min_score == 0.99 and not own.min_score_overridden
    assert own.developers[0].ranked == 0  # nothing reaches 0.99
    forced = evaluate(dataset, strict, min_score=0.1, top_n=50, override=True)
    assert forced.min_score == 0.1 and forced.min_score_overridden
    assert forced.developers[0].ranked == 1
    data = forced.as_dict()
    assert data["min_score_overridden"] is True and data["min_score_basis"] == "score"


@pytest.mark.django_db
def test_subsets_only_for_mixed_datasets() -> None:
    spec = stored_config("v2-deterministic")
    single = evaluate(parse(minimal()), spec, min_score=0.1, top_n=50)
    assert single.subsets == {}

    raw = minimal()
    real = copy.deepcopy(raw["developers"][0])
    real |= {"id": "real-a", "kind": "real", "judgments": {"bench/go-proxy": 1}}
    raw["developers"].append(real)
    mixed = evaluate(parse(raw), spec, min_score=0.1, top_n=50)
    assert set(mixed.subsets) == {"persona", "real"}
    persona, found = mixed.developers
    assert mixed.subsets["persona"] == persona.metrics  # one developer each: its own metrics
    assert mixed.subsets["real"] == found.metrics
    assert mixed.as_dict()["subsets"] == mixed.subsets


@pytest.mark.django_db
def test_uncertainty_on_the_seed_benchmark() -> None:
    dataset = load(DEFAULT_DATASET)
    v1, v2 = (
        evaluate(dataset, stored_config(v), min_score=0.1, top_n=50)
        for v in ("v1-deterministic", "v2-deterministic")
    )
    found = uncertainty(v1, v2)

    assert set(found) == set(METRICS)
    assert found == uncertainty(v1, v2)  # fixed seed
    for name, interval in found.items():
        expected = sum(
            b.values[name] - a.values[name]
            for a, b in zip(v1.developers, v2.developers, strict=True)
        ) / len(v1.developers)
        assert interval.diff == pytest.approx(expected)
        assert interval.low <= interval.diff <= interval.high
    assert compare(v1, [v2])[0].improvement is False  # the verdict does not read the intervals


def test_uncertainty_needs_the_same_developers() -> None:
    one = Report("a", "d", 0.1, 50, {}, (DeveloperResult("dev-a", (), 0, 0, {}),))
    other = Report("b", "d", 0.1, 50, {}, (DeveloperResult("dev-b", (), 0, 0, {}),))
    with pytest.raises(ValueError, match="different developers"):
        uncertainty(one, other)


def test_improvement_verdict_ignores_the_interval() -> None:
    def dev_result(dev_id: str, ndcg: float) -> DeveloperResult:
        values = {name: 0.5 for name in METRICS} | {"ndcg@10": ndcg}
        return DeveloperResult(dev_id, (), 0, 0, values)

    def built(label: str, ndcgs: list[float]) -> Report:
        devs = tuple(dev_result(f"dev-{i}", v) for i, v in enumerate(ndcgs))
        means = {name: 0.5 for name in METRICS} | {"ndcg@10": round(sum(ndcgs) / len(ndcgs), 4)}
        return Report(label, "d", 0.1, 50, means, devs)

    base = built("base", [0.5] * 6)
    candidate = built("candidate", [0.9] + [0.5] * 5)  # better for one developer of six

    interval = uncertainty(base, candidate)["ndcg@10"]
    assert interval.low <= 0 < interval.high and not interval.marked
    assert compare(base, [candidate])[0].improvement is True
