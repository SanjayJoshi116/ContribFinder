"""Issue matching, issue signals, v2 configuration and recommended issues (Phase 7, group 5)."""

import copy
from datetime import timedelta

import pytest
from django.apps import apps
from django.utils import timezone

from developers.models import DeveloperProfile
from issues.models import Issue, RecommendedIssue
from recommendations.models import Recommendation, ScoringConfig
from services import feedback
from services.matching.features import DeveloperFeatures, SkillFeature
from services.matching.issues import (
    NO_MATCH,
    IssueFeature,
    load_issues,
    match_issues,
    score_issue,
)
from services.ranking.config import V2_ISSUE_PARAMS
from services.ranking.explain import reasons

from .repo_fixtures import make_issue
from .test_recommendation_generation import (  # noqa: F401 - pytest fixtures
    developer,
    generate,
    pool,
    ready_repo,
)

pytestmark = [pytest.mark.respx(assert_all_called=False)]

NOW = timezone.now()
PARAMS = V2_ISSUE_PARAMS


def dev(level: str = "beginner", **skills: float) -> DeveloperFeatures:
    skills = skills or {"django": 0.8, "python": 0.9}
    return DeveloperFeatures(
        skills={
            slug: SkillFeature(conf, "framework", slug.title(), 1) for slug, conf in skills.items()
        },
        interests={},
        experience_level=level,
    )


def issue(
    number: int = 1,
    *,
    labels=(),
    techs=("django",),
    difficulty="unknown",
    ctype="unknown",
    age_days: float = 1,
) -> IssueFeature:
    return IssueFeature(
        id=number,
        repository_id=1,
        number=number,
        labels=tuple(labels),
        contribution_type=ctype,
        difficulty=difficulty,
        technologies=tuple(techs),
        updated_at=NOW - timedelta(days=age_days),
    )


# --- pure scoring ------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["beginner", "intermediate", "experienced", "unknown"])
@pytest.mark.parametrize("difficulty", ["beginner", "intermediate", "advanced", "unknown"])
def test_difficulty_fit_comes_from_the_table(level: str, difficulty: str) -> None:
    _, fit, _, _ = score_issue(issue(difficulty=difficulty), dev(level), PARAMS)
    assert fit == PARAMS["difficulty_fit"][level][difficulty]


def test_issue_score_parts() -> None:
    tech, fit, approach, scored = score_issue(
        issue(labels=("good_first_issue",), techs=("django", "react"), difficulty="beginner"),
        dev("beginner"),
        PARAMS,
    )
    assert (tech, fit, approach) == (0.4, 1.0, 1.0)  # Django 0.8 of two technologies
    assert scored.score == round(0.6 * 0.4 + 0.25 * 1.0 + 0.15 * 1.0, 4)


def test_help_wanted_is_less_approachable() -> None:
    _, _, approach, _ = score_issue(issue(labels=("help_wanted",)), dev(), PARAMS)
    assert approach == 0.6
    _, _, both, _ = score_issue(issue(labels=("help_wanted", "good_first_issue")), dev(), PARAMS)
    assert both == 1.0


def test_matching_issue_is_relevant() -> None:
    match = match_issues([issue(difficulty="beginner")], dev("beginner"), PARAMS)
    assert [m.issue.number for m in match.issues] == [1]


def test_unrelated_issue_is_not_relevant() -> None:
    params = {**PARAMS, "min_score": 0.0}  # the rule holds whatever the minimum score
    unrelated = issue(techs=("rust",), difficulty="beginner")
    assert match_issues([unrelated], dev("beginner"), params) == NO_MATCH


def test_approachable_issue_without_technology_is_relevant() -> None:
    gfi = issue(labels=("good_first_issue",), techs=(), difficulty="beginner")
    assert len(match_issues([gfi], dev("beginner"), PARAMS).issues) == 1


def test_below_minimum_score_is_not_relevant() -> None:
    weak = issue(techs=("django", "react", "vue", "rust"), difficulty="advanced")  # tech 0.2
    assert match_issues([weak], dev("beginner"), PARAMS) == NO_MATCH


def test_cap_and_order() -> None:
    issues = [issue(n, age_days=n) for n in range(1, 13)]
    issues.append(issue(20, labels=("good_first_issue",), age_days=50))
    match = match_issues(issues, dev(), PARAMS)
    assert [m.issue.number for m in match.issues] == [20, 1, 2, 3, 4]  # best, then most recent


def test_issue_fit_saturates() -> None:
    one = match_issues([issue(difficulty="beginner")], dev("beginner"), PARAMS)
    score = one.issues[0].score
    assert one.issue_fit.value == round(score / PARAMS["saturation"], 4)
    many = match_issues(
        [issue(n, difficulty="beginner", labels=("good_first_issue",)) for n in range(1, 6)],
        dev("beginner"),
        PARAMS,
    )
    assert many.issue_fit.value == 1.0
    assert many.issue_fit.evidence == ({"count": 5, "by_type": {"unknown": 5}},)


def test_difficulty_fit_ignores_unknown() -> None:
    match = match_issues([issue(1), issue(2)], dev("beginner"), PARAMS)
    assert match.issue_fit.value > 0
    assert match.difficulty_fit.value == 0 and match.difficulty_fit.evidence == ()


def test_difficulty_fit_is_the_best_known_fit() -> None:
    match = match_issues(
        [issue(1, difficulty="advanced"), issue(2, difficulty="beginner"), issue(3)],
        dev("intermediate"),
        PARAMS,
    )
    assert match.difficulty_fit.value == 0.7
    (evidence,) = match.difficulty_fit.evidence
    assert evidence["best"] == "beginner"
    assert evidence["by_difficulty"] == {"advanced": 1, "beginner": 1, "unknown": 1}
    assert "intermediate" not in str(evidence)  # the experience level is never evidence


def test_issue_reasons_from_non_zero_parts_only() -> None:
    full = match_issues(
        [issue(labels=("good_first_issue",), difficulty="beginner")], dev("beginner"), PARAMS
    ).issues[0]
    assert [r["type"] for r in full.reasons] == ["technology", "difficulty", "approachability"]
    texts = " ".join(r["text"] for r in full.reasons)
    assert "Django" in texts and "beginner" in texts and "estimated" in texts.lower()
    assert '"good first issue"' in texts and "%" not in texts

    bare = match_issues([issue(difficulty="unknown")], dev(), PARAMS).issues[0]
    assert [r["type"] for r in bare.reasons] == ["technology"]


def test_no_issue_params_means_no_match() -> None:
    assert match_issues([issue(difficulty="beginner")], dev(), None) == NO_MATCH


def test_matching_is_deterministic() -> None:
    issues = [issue(n, difficulty="beginner", age_days=1) for n in range(1, 8)]
    assert match_issues(issues, dev(), PARAMS) == match_issues(
        list(reversed(issues)), dev(), PARAMS
    )


# --- repository reasons -------------------------------------------------------------------


def test_issue_reasons_on_the_recommendation() -> None:
    match = match_issues(
        [
            issue(1, difficulty="beginner", ctype="documentation"),
            issue(2, difficulty="beginner", ctype="bug_fix"),
            issue(3, ctype="bug_fix"),
        ],
        dev("beginner"),
        PARAMS,
    )
    found = {
        r.type: r
        for r in reasons(
            {"issue_fit": match.issue_fit, "difficulty_fit": match.difficulty_fit},
            {"issue_fit": 0.05, "difficulty_fit": 0.05},
        )
    }
    assert found["issue_availability"].text == (
        "3 open issues match your profile, including 2 bug fix issues"
    )
    assert found["difficulty"].text == "Some issues look beginner-level (estimated)"
    assert all("%" not in r.text for r in found.values())


def test_no_issue_reasons_without_issues() -> None:
    assert (
        reasons({"issue_fit": NO_MATCH.issue_fit, "difficulty_fit": NO_MATCH.difficulty_fit}, {})
        == []
    )


# --- database: loading and generation -----------------------------------------------------


@pytest.mark.django_db
def test_load_issues_keeps_eligible_only(pool) -> None:  # noqa: F811
    repo = pool["django"]
    make_issue(repo, 1)
    make_issue(repo, 2, has_assignee=True)
    make_issue(repo, 3, is_locked=True)
    make_issue(repo, 4, github_updated_at=timezone.now() - timedelta(days=400))
    make_issue(repo, 5, state="closed")
    loaded = load_issues([repo.pk, pool["plain"].pk], timezone.now(), 365)
    assert [i.number for i in loaded[repo.pk]] == [1]
    assert pool["plain"].pk not in loaded


def django_issues(repo, count: int = 3, **fields) -> list[Issue]:
    updated = timezone.now() - timedelta(days=1)
    defaults = {
        "github_updated_at": updated,
        "labels": ["good_first_issue"],
        "difficulty": "beginner",
        "contribution_type": "documentation",
        "technologies": [{"slug": "django", "source": "title"}],
    }
    return [make_issue(repo, n, **{**defaults, **fields}) for n in range(1, count + 1)]


@pytest.mark.django_db
def test_generation_stores_relevant_issues_and_reasons(user, developer, pool) -> None:  # noqa: F811
    DeveloperProfile.objects.filter(pk=developer.pk).update(experience_level="beginner")
    django_issues(pool["django"])
    make_issue(pool["django"], 9, has_assignee=True, labels=["good_first_issue"])

    generate(user)

    rec = Recommendation.objects.get(repository=pool["django"])
    stored = list(rec.recommended_issues.order_by("rank"))
    assert [ri.issue.number for ri in stored] == [1, 2, 3]
    assert [ri.rank for ri in stored] == [1, 2, 3]
    assert stored[0].reasons and all("%" not in r["text"] for r in stored[0].reasons)
    assert rec.relevant_issue_count == 3
    assert rec.issue_difficulties == ["beginner"]
    assert rec.issue_contribution_types == ["documentation"]
    assert rec.signal_scores["issue_fit"] > 0 and rec.signal_scores["difficulty_fit"] == 1.0
    types = {r.type: r.text for r in rec.reasons.all()}
    assert types["issue_availability"].startswith("3 open issues match your profile")
    assert types["difficulty"] == "Some issues look beginner-level (estimated)"
    plain = Recommendation.objects.get(repository=pool["plain"])
    assert plain.relevant_issue_count == 0 and plain.issue_difficulties == []
    assert "issue_availability" not in {r.type for r in plain.reasons.all()}


@pytest.mark.django_db
def test_issues_alone_do_not_make_a_recommendation(user, developer, pool) -> None:  # noqa: F811
    django_issues(pool["go"], 5, technologies=[])  # approachable, but nothing matches
    generate(user)
    assert not Recommendation.objects.filter(repository=pool["go"]).exists()
    assert not RecommendedIssue.objects.filter(issue__repository=pool["go"]).exists()


@pytest.mark.django_db
def test_regeneration_replaces_recommended_issues(user, developer, pool) -> None:  # noqa: F811
    first, second, third = django_issues(pool["django"])
    generate(user)
    rec = Recommendation.objects.get(repository=pool["django"])

    first.delete()  # closed on GitHub, removed by the next issue refresh
    Issue.objects.filter(pk=second.pk).update(has_assignee=True)
    generate(user)

    rec.refresh_from_db()
    assert [ri.issue_id for ri in rec.recommended_issues.all()] == [third.pk]
    assert rec.relevant_issue_count == 1
    assert RecommendedIssue.objects.count() == 1


@pytest.mark.django_db
def test_dismissed_recommendation_loses_its_issues(user, developer, pool) -> None:  # noqa: F811
    django_issues(pool["django"])
    generate(user)
    feedback.dismiss(user, Recommendation.objects.get(repository=pool["django"]))
    assert not RecommendedIssue.objects.exists()
    assert Issue.objects.count() == 3  # shared data stays


@pytest.mark.django_db
def test_v1_scores_without_issue_signals(user, developer, pool) -> None:  # noqa: F811
    django_issues(pool["django"])
    ScoringConfig.objects.update(is_active=False)
    ScoringConfig.objects.filter(version="v1-deterministic").update(is_active=True)

    generate(user)

    rec = Recommendation.objects.get(repository=pool["django"])
    assert rec.scoring_config.version == "v1-deterministic"
    assert rec.signal_scores["issue_fit"] == 0 and rec.signal_scores["difficulty_fit"] == 0
    assert rec.relevant_issue_count == 0
    assert not RecommendedIssue.objects.exists()


@pytest.mark.django_db
def test_issue_signals_change_the_score(user, developer, pool) -> None:  # noqa: F811
    generate(user)
    before = Recommendation.objects.get(repository=pool["django"]).score
    django_issues(pool["django"])
    generate(user)
    after = Recommendation.objects.get(repository=pool["django"]).score
    assert after > before


@pytest.mark.django_db
def test_generation_is_deterministic(user, developer, pool) -> None:  # noqa: F811
    django_issues(pool["django"], 6)

    def state():
        return [
            (ri.recommendation.repository_id, ri.issue_id, ri.rank, ri.score, ri.reasons)
            for ri in RecommendedIssue.objects.select_related("recommendation").order_by(
                "recommendation__rank", "rank"
            )
        ]

    generate(user)
    first = state()
    generate(user)
    assert state() == first and len(first) == 5  # capped per recommendation


@pytest.mark.django_db
def test_upgrade_migration_activates_v2() -> None:
    from importlib import import_module

    seed = import_module("recommendations.migrations.0003_seed_v2_deterministic")
    ScoringConfig.objects.filter(version="v2-deterministic").delete()
    ScoringConfig.objects.filter(version="v1-deterministic").update(is_active=True)

    seed.seed(apps, None)

    active = ScoringConfig.objects.get(is_active=True)
    assert active.version == "v2-deterministic"
    assert active.params["issues"] == copy.deepcopy(PARAMS)


@pytest.mark.django_db
def test_upgrade_regenerates_under_v2(user, developer, pool) -> None:  # noqa: F811
    from services.ranking import freshness

    ScoringConfig.objects.update(is_active=False)
    ScoringConfig.objects.filter(version="v1-deterministic").update(is_active=True)
    generate(user)
    assert freshness.due_profiles() == []
    ScoringConfig.objects.update(is_active=False)
    ScoringConfig.objects.filter(version="v2-deterministic").update(is_active=True)
    assert [p.pk for p in freshness.due_profiles()] == [developer.pk]


@pytest.mark.django_db
def test_issue_refresh_makes_recommendations_due(user, developer, pool, respx_mock) -> None:  # noqa: F811
    from services.github.client import GitHubClient
    from services.ranking import freshness
    from services.repositories.analysis import RepositoryAnalysisService

    from .repo_fixtures import API, issue_payload
    from .test_github_client import TOKEN

    repo = pool["django"]
    generate(user)
    respx_mock.get(f"{API}/repos/{repo.full_name}/issues").respond(200, json=[issue_payload(1)])
    with GitHubClient(TOKEN, cache_scope="public") as client:
        RepositoryAnalysisService(client).run(repo.pk, ["issues"])
    assert [p.pk for p in freshness.due_profiles()] == [developer.pk]
