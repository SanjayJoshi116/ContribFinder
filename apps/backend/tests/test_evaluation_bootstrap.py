"""Paired bootstrap over developers (change evaluation-confidence, group 1). Pure."""

import pytest

from services.evaluation.bootstrap import DEFAULT_RESAMPLES, MIN_MARKED_DEVELOPERS, paired

BASE = [0.5, 0.6, 0.7, 0.4, 0.8, 0.9]


def test_same_inputs_and_seed_give_the_same_interval() -> None:
    candidate = [0.6, 0.55, 0.8, 0.4, 0.85, 0.9]
    assert paired(BASE, candidate) == paired(BASE, candidate)
    assert paired(BASE, candidate, seed=1) == paired(BASE, candidate, seed=1)


def test_one_better_of_six_is_noise() -> None:
    candidate = [BASE[0] + 0.3, *BASE[1:]]
    found = paired(BASE, candidate)
    assert found.diff == pytest.approx(0.05)
    assert found.low == 0 and found.high > 0
    assert not found.marked
    # A resample misses the one better developer with probability (5/6)^6 ≈ 0.335.
    assert found.not_better == pytest.approx((5 / 6) ** 6, abs=0.02)


def test_every_developer_better_is_marked() -> None:
    found = paired(BASE, [v + 0.1 for v in BASE])
    assert found.low > 0 and found.marked and found.not_better == 0


def test_every_developer_worse_is_marked() -> None:
    found = paired(BASE, [v - 0.1 for v in BASE])
    assert found.high < 0 and found.marked and found.not_better == 1


def test_identical_rankings() -> None:
    found = paired(BASE, BASE)
    assert (found.diff, found.low, found.high, found.not_better) == (0, 0, 0, 1)
    assert not found.marked


def test_one_developer_has_a_zero_width_interval() -> None:
    found = paired([0.4], [0.7])
    assert found.low == found.high == found.diff == pytest.approx(0.3)
    assert found.not_better == 0
    assert not found.marked and found.too_few


def test_four_developers_all_better_are_too_few_to_mark() -> None:
    found = paired(BASE[:4], [v + 0.1 for v in BASE[:4]])
    assert found.low > 0 and found.not_better == 0
    assert not found.marked and found.too_few
    assert found.as_dict()["developers"] == 4 and found.as_dict()["too_few"] is True


def test_six_developers_is_the_minimum_to_mark() -> None:
    assert MIN_MARKED_DEVELOPERS == 6
    found = paired(BASE, [v + 0.1 for v in BASE])
    assert found.marked and not found.too_few
    assert found.as_dict()["developers"] == 6 and found.as_dict()["too_few"] is False


def test_interval_depends_only_on_its_own_inputs() -> None:
    # One generator per call: computing another comparison first changes nothing.
    candidate = [0.6, 0.55, 0.8, 0.4, 0.85, 0.9]
    alone = paired(BASE, candidate)
    paired(BASE, [v + 0.2 for v in BASE])
    assert paired(BASE, candidate) == alone


def test_interval_contains_the_observed_difference() -> None:
    candidate = [0.6, 0.55, 0.8, 0.4, 0.85, 0.9]
    found = paired(BASE, candidate, resamples=DEFAULT_RESAMPLES)
    assert found.low <= found.diff <= found.high


@pytest.mark.parametrize(
    ("baseline", "candidate", "resamples"),
    [([0.1, 0.2], [0.1], 10), ([], [], 10), ([0.1], [0.2], 0)],
    ids=["unequal", "empty", "no-resamples"],
)
def test_invalid_input(baseline, candidate, resamples) -> None:
    with pytest.raises(ValueError):
        paired(baseline, candidate, resamples=resamples)
