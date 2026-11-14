"""Repository technologies and relevance signals (Phase 5, group 3). Pure functions."""

from dataclasses import replace

import pytest

from services.matching import signals
from services.matching.features import DeveloperFeatures, RepoData, SkillFeature, SnapshotData
from services.matching.technologies import repository_technologies
from services.ranking import explain
from services.ranking.config import V1_PARAMS
from services.ranking.score import contributions

SOURCES = V1_PARAMS["tech_sources"]


def dev(skills=None, interests=None) -> DeveloperFeatures:
    return DeveloperFeatures(
        skills={
            slug: SkillFeature(conf, cat, slug.title(), repos)
            for slug, (conf, cat, repos) in (skills or {}).items()
        },
        interests=interests or {},
    )


def repo(**kw) -> RepoData:
    base = RepoData(
        id=1,
        full_name="encode/httpx",
        description="",
        languages=(),
        topics=(),
        dependencies=(),
        has_contributing=False,
        has_issue_templates=False,
        has_good_first_issue_label=False,
        has_help_wanted_label=False,
        snapshot=None,
        best_search_rank=None,
    )
    return replace(base, **kw)


DJANGO_REPO = repo(
    languages=(("Python", 800), ("HTML", 200)),
    topics=("django", "developer-tools"),
    dependencies=(("pypi", "django"), ("pypi", "celery")),
)
PY_DEV = dev(
    {
        "python": (0.9, "language", 8),
        "django": (0.8, "framework", 5),
        "html": (0.2, "language", 0),
    },
    {"developer-tooling": ("Developer tooling", 0.7)},
)


def techs(r: RepoData = DJANGO_REPO):
    return repository_technologies(r.languages, r.topics, r.dependencies, SOURCES)


def test_technologies_from_all_sources() -> None:
    t = techs()
    assert set(t) == {"python", "html", "django", "celery"}
    assert (t["python"].category, t["python"].share, t["python"].weight) == ("language", 0.8, 0.8)
    assert t["django"].category == "framework"
    assert set(t["django"].sources) == {"topic", "dependency"}
    assert t["django"].weight == 1.0  # max of topic 0.6 and dependency 1.0
    assert t["celery"].sources == ("dependency",)


def test_empty_repository_has_no_technologies_and_zero_signals() -> None:
    empty = repo()
    assert techs(empty) == {}
    for fn in (signals.skill_match, signals.language_match, signals.framework_match):
        assert fn({}, PY_DEV) == signals.ZERO


def test_language_match_weights_share_by_confidence() -> None:
    s = signals.language_match(techs(), PY_DEV)
    assert s.value == pytest.approx(0.8 * 0.9 + 0.2 * 0.2)
    assert [e["slug"] for e in s.evidence] == ["python", "html"]


def test_skill_match_is_weighted_coverage() -> None:
    t = techs()
    s = signals.skill_match(t, PY_DEV)
    total = sum(x.weight for x in t.values())
    expected = (0.8 * 0.9 + 0.2 * 0.2 + 1.0 * 0.8) / total  # celery unknown to the developer
    assert s.value == pytest.approx(round(expected, 4))
    assert "celery" not in {e["slug"] for e in s.evidence}


def test_readme_only_skill_counts_at_low_confidence() -> None:
    readme_only = dev({"django": (0.2, "framework", 0)})
    assert signals.framework_match(techs(), readme_only).value == pytest.approx(0.2)


def test_framework_match_noisy_or_and_zero_without_frameworks() -> None:
    s = signals.framework_match(techs(), PY_DEV)
    assert s.value == pytest.approx(0.8)
    assert s.evidence[0] == {"slug": "django", "name": "Django", "confidence": 0.8, "repo_count": 5}
    no_framework = repo(languages=(("Python", 100),))
    assert signals.framework_match(techs(no_framework), PY_DEV) == signals.ZERO


def test_interest_via_topic_and_description() -> None:
    by_topic = signals.interest_match(DJANGO_REPO, PY_DEV)
    assert by_topic.value == pytest.approx(0.7)
    assert by_topic.evidence[0]["via"] == "topic"
    by_text = signals.interest_match(repo(description="A command line tool for teams"), PY_DEV)
    assert (by_text.evidence[0]["via"], by_text.evidence[0]["match"]) == (
        "description",
        "command line tool",
    )
    assert signals.interest_match(repo(), PY_DEV) == signals.ZERO


def test_activity_without_snapshot_is_zero() -> None:
    assert signals.activity_signal(repo(), V1_PARAMS["activity"]) == signals.ZERO
    snap = SnapshotData("moderately_active", 40, 3, 1, 12)
    s = signals.activity_signal(repo(snapshot=snap), V1_PARAMS["activity"])
    assert s.value == 0.6
    assert s.evidence[0]["label"] == "moderately_active"


def test_openness_sums_and_caps() -> None:
    points = V1_PARAMS["openness"]
    s = signals.contribution_openness(
        repo(has_contributing=True, has_good_first_issue_label=True), points
    )
    assert s.value == pytest.approx(0.7)
    assert [e["flag"] for e in s.evidence] == ["contributing", "good_first_issue"]
    everything = repo(
        has_contributing=True,
        has_issue_templates=True,
        has_good_first_issue_label=True,
        has_help_wanted_label=True,
    )
    assert signals.contribution_openness(everything, {k: 0.5 for k in points}).value == 1.0


def test_signals_are_deterministic() -> None:
    first = [signals.skill_match(techs(), PY_DEV), signals.interest_match(DJANGO_REPO, PY_DEV)]
    second = [signals.skill_match(techs(), PY_DEV), signals.interest_match(DJANGO_REPO, PY_DEV)]
    assert first == second


def test_skill_evidence_names_only_technologies_that_added_to_the_value() -> None:
    k8s_dev = dev({"python": (0.9, "language", 3), "kubernetes": (0.7, "devops", 2)})
    tagged = repo(languages=(("Python", 900),), topics=("kubernetes",))
    no_topics = {**SOURCES, "topic": 0.0}
    t = repository_technologies(tagged.languages, tagged.topics, tagged.dependencies, no_topics)
    s = signals.skill_match(t, k8s_dev)
    assert [e["slug"] for e in s.evidence] == ["python"]
    assert s.value == pytest.approx(0.9)  # Kubernetes (weight 0) added nothing before either


def test_framework_from_a_source_weighted_zero_does_not_count() -> None:
    """RNK-3: tagged ``django`` but not depending on it, with topics weighted 0."""
    tagged = repo(languages=(("Python", 900),), topics=("django",))
    no_topics = {**SOURCES, "topic": 0.0}
    t = repository_technologies(tagged.languages, tagged.topics, tagged.dependencies, no_topics)
    assert t["django"].weight == 0
    framework = signals.framework_match(t, PY_DEV)
    assert framework == signals.ZERO
    sigs = {"framework": framework}
    assert explain.reasons(sigs, contributions(sigs, {"framework": 0.1}, {})) == []


def test_openness_evidence_names_only_flags_worth_points() -> None:
    """RNK-4: issue templates worth 0 points add nothing and are not named."""
    points = {**V1_PARAMS["openness"], "issue_templates": 0.0}
    s = signals.contribution_openness(repo(has_contributing=True, has_issue_templates=True), points)
    assert s.value == pytest.approx(points["contributing"])
    assert [e["flag"] for e in s.evidence] == ["contributing"]
    sigs = {"openness": s}
    (reason,) = explain.reasons(sigs, contributions(sigs, {"openness": 0.05}, {}))
    assert reason.text == "Has a contributing guide"


def test_language_share_rounding_to_zero_is_not_named() -> None:
    go_dev = dev({"python": (0.9, "language", 3), "go": (0.9, "language", 1)})
    tiny = repo(languages=(("Python", 1_000_000), ("Go", 1)))
    t = repository_technologies(tiny.languages, tiny.topics, tiny.dependencies, SOURCES)
    assert [e["slug"] for e in signals.language_match(t, go_dev).evidence] == ["python"]
    assert [e["slug"] for e in signals.skill_match(t, go_dev).evidence] == ["python"]


def test_matching_key_lists_match_configuration_validation() -> None:
    """MAT-7: a key added on one side only would raise KeyError in generation or never score."""
    from repositories.models import ActivityLabel
    from services.matching.technologies import DEPENDENCY_SOURCE, TOPIC_SOURCE
    from services.ranking import config

    assert {key for key, _ in signals.OPENNESS_FLAGS} == set(config.OPENNESS_KEYS)
    assert set(ActivityLabel.values) == set(config.ACTIVITY_KEYS)
    assert {DEPENDENCY_SOURCE, TOPIC_SOURCE} == set(config.TECH_SOURCE_KEYS)
