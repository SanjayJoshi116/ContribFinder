from datetime import UTC, datetime, timedelta

from django.conf import settings

from services.profiling.experience import estimate_experience, experience_signals
from services.profiling.languages import aggregate_languages
from services.profiling.summary import SPARSE, build_summary

from .profiling_fixtures import NOW, contribution, profile, repo

THRESHOLDS = settings.EXPERIENCE_THRESHOLDS


def level(p, skills: int = 0) -> str:
    return estimate_experience(experience_signals(p, skills), THRESHOLDS)[0]


# --- experience ------------------------------------------------------------------------


def test_experienced_from_multiple_signals() -> None:
    p = profile(
        account_created_at=NOW - timedelta(days=6 * 365),
        owned=tuple(repo() for _ in range(15)),
        contributions=(
            *(contribution(prs=4) for _ in range(5)),
            contribution(prs=5),
        ),
    )
    assert level(p, skills=10) == "experienced"


def test_unknown_with_insufficient_signals() -> None:
    p = profile(account_created_at=NOW - timedelta(days=14))
    assert level(p) == "unknown"


def test_repository_count_alone_does_not_decide() -> None:
    p = profile(owned=tuple(repo() for _ in range(50)))
    assert level(p) == "unknown"


def test_beginner_and_intermediate() -> None:
    young = profile(account_created_at=NOW - timedelta(days=100), owned=(repo(),))
    assert level(young) == "beginner"
    middle = profile(
        account_created_at=NOW - timedelta(days=2 * 365),
        owned=tuple(repo() for _ in range(4)),
        contributions=(contribution(prs=2),),
    )
    assert level(middle, skills=4) == "intermediate"


def test_inactive_repositories_do_not_count() -> None:
    old = datetime(2020, 1, 1, tzinfo=UTC)
    p = profile(owned=tuple(repo(pushed_at=old) for _ in range(5)))
    assert "active_repositories" not in experience_signals(p, 0)


def test_audit_contains_signals_and_scores() -> None:
    p = profile(account_created_at=NOW - timedelta(days=5 * 365), owned=(repo(),))
    _, audit = estimate_experience(experience_signals(p, 0), THRESHOLDS)
    assert audit["scores"] == {"account_age_years": 2, "active_repositories": 0}


# --- languages -------------------------------------------------------------------------


def test_language_aggregation() -> None:
    p = profile(
        owned=(
            repo(languages={"Python": 7000, "TypeScript": 3000}),
            repo(languages={"Python": 1000}),
            repo(languages={"Rust": 99999}, is_fork=True),
        )
    )
    assert aggregate_languages(p) == [
        {"name": "Python", "bytes": 8000, "share": 0.73, "repo_count": 2},
        {"name": "TypeScript", "bytes": 3000, "share": 0.27, "repo_count": 1},
    ]


def test_no_languages() -> None:
    assert aggregate_languages(profile()) == []


# --- summary ---------------------------------------------------------------------------


def test_summary_mentions_only_signals() -> None:
    summary = build_summary(
        ["Python", "TypeScript", "Go"],
        ["Django", "React", "Celery", "Redux"],
        ["Developer tooling", "AI / machine learning", "Security"],
    )
    assert summary == (
        "Works mostly in Python and TypeScript. Frequently uses Django, React and Celery. "
        "Interested in developer tooling and AI / machine learning."
    )


def test_summary_keeps_acronyms() -> None:
    assert build_summary(["Go"], [], ["DevOps"]) == "Works mostly in Go. Interested in DevOps."


def test_sparse_summary() -> None:
    assert build_summary([], [], []) == SPARSE


def test_summary_ranks_languages_by_evidence_not_bytes() -> None:
    from services.profiling.analysis import AnalysisConfig, analyze

    p = profile(
        readme="## Skills\nPython, Docker",
        owned=(
            repo(languages={"Jupyter Notebook": 90000, "HTML": 30000, "Python": 5000}),
            repo(languages={"TypeScript": 5000, "HTML": 9000}, deps=[("npm", "react", "p")]),
            repo(languages={"Python": 4000}),
        ),
    )
    summary = analyze(p, AnalysisConfig.from_settings()).summary
    # Python has the most evidence; HTML is markup; Docker is only a README mention.
    assert summary.startswith("Works mostly in Python and TypeScript. Frequently uses React.")
