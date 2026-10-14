"""Recommendation reasons from signal evidence (spec: recommendation-explanations; design D6).

Pure. One reason per non-zero signal; its text is filled only from that signal's evidence, so
nothing is claimed that scoring did not use. Shares and confidences become words: no "%".
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from services.matching.signals import Signal

from .score import contributions

ORDER = (
    "skill",
    "language",
    "framework",
    "interest",
    "issue_availability",
    "difficulty",
    "activity",
    "openness",
)
# Recommendation reason type per signal, where the two differ.
REASON_TYPES = {"issue_fit": "issue_availability", "difficulty_fit": "difficulty"}

ACTIVITY_TEXT = {
    "recently_active": "Recently active",
    "moderately_active": "Moderately active",
    "low_activity": "Low recent activity",
}
OPENNESS_TEXT = {
    "contributing": "a contributing guide",
    "good_first_issue": "good first issue labels",
    "help_wanted": "help wanted labels",
    "issue_templates": "issue templates",
}


CONTRIBUTION_TYPE_TEXT = {
    "code": "code",
    "documentation": "documentation",
    "testing": "testing",
    "bug_fix": "bug fix",
    "feature": "feature",
    "devops": "DevOps",
    "design": "design",
}


@dataclass(frozen=True)
class Reason:
    type: str
    text: str
    weight: float
    detail: dict[str, Any]


def join(names: Sequence[str]) -> str:
    """``A``, ``A and B``, ``A, B and C``."""
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _skill(items: Sequence[Mapping[str, Any]]) -> str:
    return f"Shares {join([i['name'] for i in items])} with your profile"


def _language(items: Sequence[Mapping[str, Any]]) -> str:
    first, rest = items[0], items[1:]
    share = first["share"] or 0.0
    how = "mainly" if share >= 0.5 else "partly"
    confidence = first["confidence"]
    if confidence >= 0.7:
        known = "one of your strongest languages"
    elif confidence >= 0.4:
        known = "a language you use"
    else:
        known = "a language you have touched"
    text = f"Written {how} in {first['name']}, {known}"
    if rest:
        text += f"; also uses {join([i['name'] for i in rest])}"
    return text


def _your_repositories(n: int) -> str:
    return "one of your repositories" if n == 1 else f"{n} of your repositories"


def _framework(items: Sequence[Mapping[str, Any]]) -> str:
    first = items[0]
    text = f"Uses {join([i['name'] for i in items])}"
    if first["repo_count"]:
        where = _your_repositories(first["repo_count"])
        if len(items) == 1:
            text += f", which appears in {where}"
        else:
            text += f"; {first['name']} appears in {where}"
    return text


def _interest(items: Sequence[Mapping[str, Any]]) -> str:
    first = items[0]
    via = f'topic "{first["match"]}"' if first["via"] == "topic" else f'mentions "{first["match"]}"'
    text = f"Matches your interest in {first['name'].lower()} ({via})"
    if len(items) > 1:
        text += f"; also {join([i['name'].lower() for i in items[1:]])}"
    return text


def _activity(items: Sequence[Mapping[str, Any]]) -> str:
    facts = items[0]
    text = ACTIVITY_TEXT.get(facts["label"], "Activity observed")
    details = []
    if facts.get("days_since_push") is not None:
        days = facts["days_since_push"]
        details.append("pushed today" if days == 0 else f"last push {_plural(days, 'day')} ago")
    if facts.get("commits_90d"):
        details.append(f"{_plural(facts['commits_90d'], 'commit')} in 90 days")
    if facts.get("prs_merged_90d"):
        details.append(f"{_plural(facts['prs_merged_90d'], 'merged pull request')} in 90 days")
    return f"{text}: {', '.join(details)}" if details else text


def _openness(items: Sequence[Mapping[str, Any]]) -> str:
    return f"Has {join([OPENNESS_TEXT[i['flag']] for i in items])}"


def _issue_availability(items: Sequence[Mapping[str, Any]]) -> str:
    facts = items[0]
    count = facts["count"]
    text = (
        "1 open issue matches your profile"
        if count == 1
        else f"{count} open issues match your profile"
    )
    known = [(t, n) for t, n in facts["by_type"].items() if t in CONTRIBUTION_TYPE_TEXT]
    if known:
        kind, n = min(known, key=lambda tn: (-tn[1], tn[0]))
        text += f", including {_plural(n, f'{CONTRIBUTION_TYPE_TEXT[kind]} issue')}"
    return text


def _difficulty(items: Sequence[Mapping[str, Any]]) -> str:
    facts = items[0]
    level, count = facts["best"], facts["count"]
    if count == 1:
        return f"1 issue looks {level}-level (estimated)"
    return f"Some issues look {level}-level (estimated)"


TEMPLATES: dict[str, Callable[[Sequence[Mapping[str, Any]]], str]] = {
    "skill": _skill,
    "language": _language,
    "framework": _framework,
    "interest": _interest,
    "activity": _activity,
    "openness": _openness,
    "issue_availability": _issue_availability,
    "difficulty": _difficulty,
}


def reasons(
    signals: Mapping[str, Signal],
    weights: Mapping[str, float],
    params: Mapping[str, Any] | None = None,
) -> list[Reason]:
    """Reasons for every signal above 0 with evidence, highest contribution to the score first
    (the same contributions the score sums, relevance scaling included)."""
    contribution = contributions(signals, weights, params or {})
    result = [
        Reason(
            type=REASON_TYPES.get(name, name),
            text=TEMPLATES[REASON_TYPES.get(name, name)](signal.evidence),
            weight=round(contribution[name], 4),
            detail={"items": [dict(item) for item in signal.evidence]},
        )
        for name, signal in signals.items()
        if signal.value > 0 and signal.evidence
    ]
    result.sort(key=lambda r: (-r.weight, ORDER.index(r.type)))
    return result
