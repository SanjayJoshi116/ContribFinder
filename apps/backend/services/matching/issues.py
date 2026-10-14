"""Issue matching (spec: issue-matching, recommendation-engine; design D5).

``load_issues`` is the only database access: one query for every candidate repository.
Everything else is pure. Each eligible issue is scored for the developer from technology
match, difficulty fit and approachability; the best relevant ones become the recommendation's
relevant issues and feed two repository signals, ``issue_fit`` and ``difficulty_fit``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from issues.models import Difficulty, Issue
from services.profiling.taxonomy import SKILLS_BY_SLUG
from services.ranking.config import DIFFICULTY_FIT_BEST, DIFFICULTY_FIT_WEIGHTED

from .features import DeveloperFeatures
from .signals import ZERO, Signal, signal_of

GOOD_FIRST_ISSUE = "good_first_issue"
HELP_WANTED = "help_wanted"
APPROACHABILITY_TEXT = {GOOD_FIRST_ISSUE: "good first issue", HELP_WANTED: "help wanted"}
LEVELS = (Difficulty.BEGINNER, Difficulty.INTERMEDIATE, Difficulty.ADVANCED, Difficulty.UNKNOWN)


@dataclass(frozen=True)
class IssueFeature:
    id: int
    repository_id: int
    number: int
    labels: tuple[str, ...]
    contribution_type: str
    difficulty: str
    technologies: tuple[str, ...]  # skill slugs
    updated_at: datetime | None


@dataclass(frozen=True)
class MatchedIssue:
    issue: IssueFeature
    score: float  # internal ranking value, never serialized
    reasons: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class IssueMatch:
    issues: tuple[MatchedIssue, ...] = ()
    issue_fit: Signal = ZERO
    difficulty_fit: Signal = ZERO


NO_MATCH = IssueMatch()


def load_issues(
    repository_ids: Iterable[int], now: datetime, max_age_days: int
) -> dict[int, list[IssueFeature]]:
    """Eligible issues per repository: open, not locked, unassigned and updated within
    ``max_age_days``. One query."""
    ids = list(repository_ids)
    if not ids:
        return {}
    rows = Issue.objects.filter(
        repository_id__in=ids,
        state="open",
        is_locked=False,
        has_assignee=False,
        github_updated_at__gte=now - timedelta(days=max_age_days),
    ).values_list(
        "id",
        "repository_id",
        "number",
        "labels",
        "contribution_type",
        "difficulty",
        "technologies",
        "github_updated_at",
    )
    result: dict[int, list[IssueFeature]] = {}
    for pk, repo_id, number, labels, ctype, difficulty, techs, updated in rows:
        result.setdefault(repo_id, []).append(
            IssueFeature(
                id=pk,
                repository_id=repo_id,
                number=number,
                labels=tuple(labels),
                contribution_type=ctype,
                difficulty=difficulty,
                technologies=tuple(t["slug"] for t in techs),
                updated_at=updated,
            )
        )
    return result


def _name(slug: str) -> str:
    skill = SKILLS_BY_SLUG.get(slug)
    return skill.name if skill else slug


def _join(names: Sequence[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _difficulty_text(level: str, fit: float) -> str:
    text = f"Estimated {level}-level"
    if fit >= 0.8:
        return f"{text}: a good fit"
    if fit >= 0.5:
        return f"{text}: a reasonable fit"
    return text


def score_issue(
    issue: IssueFeature, dev: DeveloperFeatures, params: Mapping[str, Any]
) -> tuple[float, float, float, MatchedIssue]:
    """``(tech, difficulty fit, approachability, scored issue)``."""
    weights = params["weights"]
    matched = [slug for slug in issue.technologies if dev.confidence(slug) > 0]
    tech = (
        sum(dev.confidence(slug) for slug in matched) / len(issue.technologies)
        if issue.technologies
        else 0.0
    )
    diff_fit = float(params["difficulty_fit"][dev.experience_level][issue.difficulty])
    approach_label = next(
        (label for label in (GOOD_FIRST_ISSUE, HELP_WANTED) if label in issue.labels), None
    )
    approach = float(params["approachability"][approach_label]) if approach_label else 0.0
    score = round(
        weights["technology"] * tech
        + weights["difficulty"] * diff_fit
        + weights["approachability"] * approach,
        4,
    )

    parts: list[tuple[float, dict[str, Any]]] = []
    if tech > 0:
        names = [_name(slug) for slug in matched]
        parts.append(
            (
                weights["technology"] * tech,
                {
                    "type": "technology",
                    "text": f"Mentions {_join(names)}, which you use",
                    "detail": {"technologies": [{"slug": s, "name": _name(s)} for s in matched]},
                },
            )
        )
    if diff_fit > 0 and issue.difficulty != Difficulty.UNKNOWN:
        parts.append(
            (
                weights["difficulty"] * diff_fit,
                {
                    "type": "difficulty",
                    "text": _difficulty_text(issue.difficulty, diff_fit),
                    "detail": {"difficulty": issue.difficulty, "estimated": True},
                },
            )
        )
    if approach_label is not None and approach > 0:
        parts.append(
            (
                weights["approachability"] * approach,
                {
                    "type": "approachability",
                    "text": f'Labeled "{APPROACHABILITY_TEXT[approach_label]}"',
                    "detail": {"label": approach_label},
                },
            )
        )
    parts.sort(key=lambda p: -p[0])
    return tech, diff_fit, approach, MatchedIssue(issue, score, tuple(r for _, r in parts))


def match_issues(
    issues: Iterable[IssueFeature], dev: DeveloperFeatures, params: Mapping[str, Any] | None
) -> IssueMatch:
    """The developer's relevant issues in one repository (best first, at most
    ``per_recommendation``) and the two repository signals they produce. ``params`` is the
    configuration's ``issues`` block; without it (v1) nothing matches."""
    if not params:
        return NO_MATCH
    relevant: list[MatchedIssue] = []
    for issue in issues:
        tech, _, approach, scored = score_issue(issue, dev, params)
        if scored.score >= params["min_score"] and (tech > 0 or approach > 0):
            relevant.append(scored)
    relevant.sort(
        key=lambda m: (
            -m.score,
            -(m.issue.updated_at.timestamp() if m.issue.updated_at else 0.0),
            m.issue.number,
        )
    )
    kept = tuple(relevant[: params["per_recommendation"]])
    if not kept:
        return NO_MATCH

    by_type = Counter(m.issue.contribution_type for m in kept)
    issue_fit = signal_of(
        sum(m.score for m in kept) / params["saturation"],
        [{"count": len(kept), "by_type": dict(sorted(by_type.items()))}],
    )

    table = params["difficulty_fit"][dev.experience_level]
    by_difficulty = Counter(m.issue.difficulty for m in kept)
    known = [level for level in LEVELS[:3] if by_difficulty[level]]
    if known:
        best = max(known, key=lambda level: (table[level], by_difficulty[level]))
        evidence: dict[str, Any] = {
            "best": str(best),
            "count": by_difficulty[best],
            "by_difficulty": {str(k): v for k, v in sorted(by_difficulty.items())},
        }
        mode = params.get("difficulty_fit_mode", DIFFICULTY_FIT_BEST)
        if mode == DIFFICULTY_FIT_WEIGHTED:
            # Score-weighted mean fit of the issues with known difficulty, scaled by issue fit:
            # one weak fitting issue no longer counts like several good ones.
            fitting = [m for m in kept if m.issue.difficulty in known]
            total = sum(m.score for m in fitting)
            mean = sum(table[m.issue.difficulty] * m.score for m in fitting) / total if total else 0
            value = mean * issue_fit.value
            evidence |= {"mode": DIFFICULTY_FIT_WEIGHTED, "mean": round(mean, 4)}
        else:
            value = float(table[best])
        difficulty_fit = signal_of(value, [evidence])
    else:
        difficulty_fit = ZERO

    return IssueMatch(issues=kept, issue_fit=issue_fit, difficulty_fit=difficulty_fit)


def snapshot(issues: Sequence[MatchedIssue]) -> dict[str, Any]:
    """The recommendation's filter snapshot of its relevant issues."""
    difficulties = {m.issue.difficulty for m in issues}
    return {
        "relevant_issue_count": len(issues),
        "issue_difficulties": [str(level) for level in LEVELS if level in difficulties],
        "issue_contribution_types": sorted({m.issue.contribution_type for m in issues}),
    }
