import pytest
from django.conf import settings

from services.profiling.confidence import compute_confidence
from services.profiling.inputs import Evidence

WEIGHTS = settings.EVIDENCE_WEIGHTS


def ev(source: str, n: int = 1) -> list[Evidence]:
    return [Evidence("python", source, i, "", None) for i in range(n)]


def conf(evidence, weights=WEIGHTS, decay=0.5, cap=0.99) -> float:
    return compute_confidence(evidence, weights, decay=decay, cap=cap)


def test_readme_only_equals_readme_weight() -> None:
    assert conf(ev("readme")) == 0.20


def test_no_evidence_is_zero() -> None:
    assert conf([]) == 0.0


def test_sustained_use_outranks_a_mention() -> None:
    assert conf(ev("language", 5) + ev("dependency", 2)) > conf(ev("readme"))


def test_monotonic() -> None:
    evidence: list[Evidence] = []
    previous = 0.0
    for source in ["readme", "topic", "language", "language", "dependency", "pull_request"]:
        evidence += ev(source)
        current = conf(evidence)
        assert current >= previous
        previous = current


def test_diminishing_returns() -> None:
    gain_2nd = conf(ev("language", 2)) - conf(ev("language", 1))
    gain_10th = conf(ev("language", 10)) - conf(ev("language", 9))
    assert 0 <= gain_10th < gain_2nd


def test_capped_below_one() -> None:
    assert conf(ev("repeated_contribution", 3) + ev("pull_request", 5)) == 0.99


def test_deterministic_and_order_independent() -> None:
    a = ev("language", 3) + ev("readme") + ev("dependency")
    assert conf(a) == conf(list(reversed(a))) == conf(a)


def test_weight_change_is_reflected() -> None:
    assert conf(ev("readme"), weights={**WEIGHTS, "readme": 0.10}) == 0.10


@pytest.mark.parametrize("source", ["unknown", "stars"])
def test_unknown_source_adds_nothing(source: str) -> None:
    assert conf(ev(source)) == 0.0
