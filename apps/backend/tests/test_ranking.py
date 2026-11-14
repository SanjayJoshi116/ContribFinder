"""Score, match labels, ranking and explanations (Phase 5, group 4). Pure functions."""

import pytest

from services.matching.features import RepoData
from services.matching.signals import ZERO, Signal
from services.ranking import explain
from services.ranking.config import V1_PARAMS, V1_WEIGHTS
from services.ranking.score import Scored, contributions, match_label, rank
from services.text import join_names

BANDS = V1_PARAMS["bands"]


def reasons_for(
    signals: dict[str, Signal], weights: dict[str, float], params=V1_PARAMS
) -> list[explain.Reason]:
    return explain.reasons(signals, contributions(signals, weights, params))


def sigs(**values: float) -> dict[str, Signal]:
    return {
        name: Signal(values[name], ({"x": 1},)) if values.get(name) else ZERO for name in V1_WEIGHTS
    }


def repo(name: str, rank_: int | None = None) -> RepoData:
    return RepoData(
        id=hash(name) % 10_000,
        full_name=name,
        description="",
        languages=(),
        topics=(),
        dependencies=(),
        has_contributing=False,
        has_issue_templates=False,
        has_good_first_issue_label=False,
        has_help_wanted_label=False,
        snapshot=None,
        best_search_rank=rank_,
    )


def scored(name: str, score: float, rank_: int | None = None, relevant: bool = True) -> Scored:
    signals = sigs(skill=0.5) if relevant else sigs(activity=1.0, openness=1.0)
    return Scored(
        repo(name, rank_), {}, signals, score, match_label(score, BANDS), relevant=relevant
    )


def test_weighted_sum_with_seed_weights() -> None:
    s = sigs(skill=1.0, language=0.5, interest=0.0, framework=1.0, activity=1.0, openness=0.4)
    assert sum(contributions(s, V1_WEIGHTS, V1_PARAMS).values()) == pytest.approx(
        0.40 + 0.10 + 0.10 + 0.10 + 0.02
    )


@pytest.mark.parametrize(
    ("score", "label"),
    [(0.60, "strong"), (0.55, "strong"), (0.40, "good"), (0.35, "good"), (0.20, "partial")],
)
def test_band_boundaries(score: float, label: str) -> None:
    assert match_label(score, BANDS) == label


def test_rank_order_tie_break_min_score_and_top_n() -> None:
    items = [
        scored("b/two", 0.5, rank_=4),
        scored("a/one", 0.5, rank_=2),
        scored("c/unranked", 0.5),
        scored("d/top", 0.9),
        scored("e/low", 0.05),
    ]
    ranked = rank(items, min_score=0.10, top_n=3)
    assert [s.repo.full_name for s in ranked] == ["d/top", "a/one", "b/two"]
    assert "e/low" not in [s.repo.full_name for s in rank(items, min_score=0.10, top_n=10)]


def test_activity_and_openness_alone_are_not_relevance() -> None:
    only_active = scored("f/active", 0.15, relevant=False)
    assert rank([only_active], min_score=0.10, top_n=10) == []


LANG = Signal(0.76, ({"slug": "python", "name": "Python", "share": 0.8, "confidence": 0.9},))
FRAMEWORK = Signal(0.8, ({"slug": "django", "name": "Django", "confidence": 0.8, "repo_count": 5},))
INTEREST = Signal(
    0.7,
    (
        {
            "slug": "developer-tooling",
            "name": "Developer tooling",
            "strength": 0.7,
            "via": "topic",
            "match": "developer-tools",
        },
    ),
)
ACTIVITY = Signal(
    1.0,
    ({"label": "recently_active", "days_since_push": 3, "commits_90d": 42, "prs_merged_90d": 0},),
)
OPEN = Signal(0.7, ({"flag": "contributing"}, {"flag": "good_first_issue"}))
SKILL = Signal(0.6, ({"slug": "python", "name": "Python"}, {"slug": "django", "name": "Django"}))


def all_signals(**overrides: Signal) -> dict[str, Signal]:
    base = {
        "skill": SKILL,
        "language": LANG,
        "framework": FRAMEWORK,
        "interest": INTEREST,
        "activity": ACTIVITY,
        "openness": OPEN,
    }
    return {**base, **overrides}


def test_reason_texts() -> None:
    texts = {r.type: r.text for r in reasons_for(all_signals(), V1_WEIGHTS)}
    assert texts == {
        "skill": "Shares Python and Django with your profile",
        "language": "Written mainly in Python, one of your strongest languages",
        "framework": "Uses Django, which appears in 5 of your repositories",
        "interest": 'Matches your interest in developer tooling (topic "developer-tools")',
        "activity": "Recently active: last push 3 days ago, 42 commits in 90 days",
        "openness": "Has a contributing guide and good first issue labels",
    }


def test_zero_signal_gives_no_reason() -> None:
    reasons = reasons_for(all_signals(interest=ZERO), V1_WEIGHTS)
    assert "interest" not in {r.type for r in reasons}


def test_weight_zero_signal_gives_no_reason() -> None:
    reasons = reasons_for(all_signals(), {**V1_WEIGHTS, "interest": 0.0})
    assert "interest" not in {r.type for r in reasons}
    assert "skill" in {r.type for r in reasons}


def test_reasons_ordered_by_contribution_with_detail() -> None:
    reasons = reasons_for(all_signals(), V1_WEIGHTS)
    weights = [r.weight for r in reasons]
    assert weights == sorted(weights, reverse=True)
    assert reasons[0].type == "skill"  # 0.40 * 0.6
    framework = next(r for r in reasons if r.type == "framework")
    assert framework.detail == {"items": [dict(FRAMEWORK.evidence[0])]}
    assert framework.weight == pytest.approx(0.08)


def test_no_percent_in_any_text() -> None:
    low = Signal(0.1, ({"slug": "go", "name": "Go", "share": 0.3, "confidence": 0.2},))
    many = Signal(
        0.9,
        tuple(
            {"slug": s, "name": s.title(), "confidence": 0.5, "repo_count": 0}
            for s in ("django", "celery", "flask")
        ),
    )
    reasons = reasons_for(all_signals(language=low, framework=many), V1_WEIGHTS)
    assert all("%" not in r.text for r in reasons)
    texts = {r.type: r.text for r in reasons}
    assert texts["language"] == "Written partly in Go, a language you have touched"
    assert texts["framework"] == "Uses Django, Celery and Flask"


def test_activity_without_details() -> None:
    bare = Signal(0.2, ({"label": "low_activity", "days_since_push": None},))
    [reason] = reasons_for({**{k: ZERO for k in V1_WEIGHTS}, "activity": bare}, V1_WEIGHTS)
    assert reason.text == "Low recent activity"


def test_join() -> None:
    assert join_names(["A"]) == "A"
    assert join_names(["A", "B"]) == "A and B"
    assert join_names(["A", "B", "C"]) == "A, B and C"
