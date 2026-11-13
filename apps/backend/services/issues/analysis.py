"""Issue analysis pipeline (spec: issue-analysis; design D4). Pure: labels → contribution
type → technologies → difficulty, from stored issue data only."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from services.profiling.text import strip_html_comments

from . import classify, labels, technologies


@dataclass(frozen=True)
class IssueInput:
    title: str
    body: str
    raw_labels: Sequence[str]
    comments: int
    max_chars: int | None = None

    def __post_init__(self) -> None:
        # Normalized once for every consumer (technologies, difficulty, the stored body): issue
        # templates leave their instructions as HTML comments, which are not the description.
        # Removed before the cap, so a long template never pushes the report out.
        object.__setattr__(self, "body", strip_html_comments(self.body)[: self.max_chars])


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
        contribution_type_evidence={**ctype_evidence, **version},  # unknown too (ISV-8)
        difficulty=level,
        difficulty_evidence={**level_evidence, **version},
        technologies=techs,
    )
