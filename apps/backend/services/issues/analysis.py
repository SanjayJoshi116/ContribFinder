"""Issue analysis pipeline (spec: issue-analysis; design D4). Pure: labels → contribution
type → technologies → difficulty, from stored issue data only."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from . import classify, labels, technologies


@dataclass(frozen=True)
class IssueInput:
    title: str
    body: str
    raw_labels: Sequence[str]
    comments: int


@dataclass(frozen=True)
class IssueAnalysis:
    labels: list[str]
    contribution_type: str
    contribution_type_evidence: dict[str, Any]
    difficulty: str
    difficulty_evidence: dict[str, Any]
    technologies: list[dict[str, str]]


def analyze(issue: IssueInput, thresholds: Mapping[str, int]) -> IssueAnalysis:
    canonical = labels.normalize_labels(issue.raw_labels)
    ctype, ctype_evidence = classify.contribution_type(canonical, issue.title)
    techs = technologies.detect(issue.title, issue.raw_labels, issue.body)
    level, level_evidence = classify.difficulty(
        raw_labels=list(issue.raw_labels),
        body=issue.body,
        technology_count=len(techs),
        contribution_type=ctype,
        comments=issue.comments,
        thresholds=thresholds,
    )
    version = {"taxonomy": labels.ISSUE_TAXONOMY_VERSION}
    return IssueAnalysis(
        labels=canonical,
        contribution_type=ctype,
        contribution_type_evidence={**ctype_evidence, **version} if ctype_evidence else {},
        difficulty=level,
        difficulty_evidence={**level_evidence, **version},
        technologies=techs,
    )
