"""Ranking metrics (Phase 8b, group 2): hand-computed values."""

import math

import pytest

from services.evaluation.metrics import (
    MRR,
    NDCG_10,
    PRECISION_5,
    PRECISION_10,
    RECALL_10,
    developer_metrics,
    mean,
    ndcg_at,
    precision_at,
    recall_at,
    reciprocal_rank,
    unjudged_at,
)


def test_spec_example() -> None:
    judgments = {"A": 2, "B": 1}
    ranking = ["B", "C", "A"]
    assert precision_at(ranking, judgments, 5) == 0.4
    assert recall_at(ranking, judgments, 10) == 1.0
    assert reciprocal_rank(ranking, judgments) == 1.0
    expected = (1 / math.log2(2) + 3 / math.log2(4)) / (3 / math.log2(2) + 1 / math.log2(3))
    assert ndcg_at(ranking, judgments, 10) == pytest.approx(expected)
    assert round(ndcg_at(ranking, judgments, 10), 4) == 0.6885
    assert unjudged_at(ranking, judgments, 10) == 1  # C


def test_short_list_is_penalized() -> None:
    judgments = {"A": 1, "B": 1, "C": 1}
    ranking = ["A", "B", "C"]
    assert precision_at(ranking, judgments, 5) == 0.6
    assert precision_at(ranking, judgments, 10) == 0.3


def test_no_relevant_result_in_the_list() -> None:
    judgments = {"A": 2, "B": 0}
    m = developer_metrics(["B", "X"], judgments)
    assert m.values == {PRECISION_5: 0.0, PRECISION_10: 0.0, RECALL_10: 0.0, MRR: 0.0, NDCG_10: 0.0}
    assert m.unjudged == 1


def test_relevant_item_cut_by_the_gate_lowers_ndcg_and_recall() -> None:
    judgments = {"A": 2, "B": 2}
    ranking = ["A"]  # B never reached the ranking
    assert recall_at(ranking, judgments, 10) == 0.5
    assert ndcg_at(ranking, judgments, 10) < 1.0


def test_perfect_ranking() -> None:
    judgments = {"A": 2, "B": 1, "C": 0}
    m = developer_metrics(["A", "B", "C"], judgments)
    assert m.values[NDCG_10] == 1.0 and m.values[MRR] == 1.0 and m.values[RECALL_10] == 1.0


def test_mrr_uses_first_relevant_rank() -> None:
    assert reciprocal_rank(["X", "Y", "A"], {"A": 1}) == pytest.approx(1 / 3)


def test_only_top_k_counts() -> None:
    ranking = [f"r{n}" for n in range(12)]
    judgments = {"r11": 2}
    assert recall_at(ranking, judgments, 10) == 0.0
    assert ndcg_at(ranking, judgments, 10) == 0.0
    assert reciprocal_rank(ranking, judgments) == pytest.approx(1 / 12)  # MRR is not cut


def test_mean_over_developers_rounded() -> None:
    a = developer_metrics(["A"], {"A": 1})
    b = developer_metrics(["X", "A"], {"A": 1})
    assert mean([a, b])[MRR] == 0.75
    assert mean([a, b])[PRECISION_5] == 0.2
