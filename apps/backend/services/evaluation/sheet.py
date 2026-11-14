"""Blind judging sheets (spec: recommendation-evaluation "Blind judging sheet", "Importing
judgments"; design D1, D2).

A sheet lists an exported developer's candidates with the facts a contributor would look at,
in alphabetical order, and nothing any scoring configuration computed: no score, signal, rank,
match label or reason. The judge fills ``grade``; ``import_sheet`` writes the grades back into
the export.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .dataset import GRADES, REAL, DatasetError, parse

COLUMNS = (
    "repository",
    "url",
    "description",
    "languages",
    "topics",
    "contribution",
    "activity",
    "open_issues",
    "grade",
    "note",
)
GUIDE = (
    "Judge each repository for the developer: would they want to contribute here?",
    "grade: 2 = highly relevant, 1 = relevant, 0 = not relevant, blank = not judged.",
    "Judge every row if you can; blank rows count as not relevant in the metrics.",
)
CONTRIBUTION_FLAGS = (
    ("has_contributing", "CONTRIBUTING"),
    ("has_issue_templates", "issue templates"),
    ("has_good_first_issue_label", "good first issue"),
    ("has_help_wanted_label", "help wanted"),
)


# A spreadsheet evaluates a cell starting with one of these (change
# services-evaluation-review-fixes, EVL-6).
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: Any) -> Any:
    """Repository text as a spreadsheet shows it, never a formula: a leading ``'``."""
    if isinstance(value, str) and value.startswith(FORMULA_STARTS):
        return f"'{value}"
    return value


# Replaces the export's request to add judgments (design D6).
JUDGED = "Real developer judged blind from a judging sheet."


class SheetError(Exception):
    pass


def _single_developer(export: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(export, Mapping):
        raise SheetError("An export must be a JSON object.")
    developers = export.get("developers")
    if not isinstance(developers, list) or len(developers) != 1:
        raise SheetError("An export must hold exactly one developer.")
    developer = developers[0]
    if not isinstance(developer, dict):
        raise SheetError("An export's developer must be a JSON object.")
    return developer


def _candidate_names(developer: Mapping[str, Any]) -> list[str]:
    """The repository name of each candidate; ``SheetError`` for any other shape."""
    candidates = developer.get("candidates", [])
    if not isinstance(candidates, list):
        raise SheetError("A developer's candidates must be a list.")
    names = []
    for index, candidate in enumerate(candidates, start=1):
        name = candidate.get("repository") if isinstance(candidate, dict) else None
        if not isinstance(name, str) or not name:
            raise SheetError(f"Candidate {index} has no repository name.")
        names.append(name)
    return names


def candidate_count(export: Mapping[str, Any]) -> int:
    """Rows a sheet of ``export`` has (validated as ``write_sheet`` validates it)."""
    return len(_candidate_names(_single_developer(export)))


def _languages(pairs: list[list[Any]]) -> str:
    """The three main languages with their share. A missing byte count counts as 0; with no
    counts at all, the first three names in their given order, without shares."""
    sized = [(name, size or 0) for name, size in pairs]
    total = sum(size for _, size in sized)
    if not total:
        return "; ".join(name for name, _ in sized[:3])
    top = sorted(sized, key=lambda p: (-p[1], p[0]))[:3]
    return "; ".join(f"{name} {round(100 * size / total)}%" for name, size in top)


def write_sheet(export: Mapping[str, Any]) -> str:
    """The sheet as CSV text; write it with ``encoding="utf-8-sig"`` (BOM for spreadsheets)."""
    developer = _single_developer(export)
    repositories = export.get("repositories", {})
    if not isinstance(repositories, Mapping):
        raise SheetError("An export's repositories must be a JSON object.")
    names = sorted(_candidate_names(developer))
    for name in names:
        if not isinstance(repositories.get(name), Mapping):
            raise SheetError(f"Candidate {name} is not described in the export's repositories.")
    out = io.StringIO()
    for line in (f"developer: {developer.get('id', '')}", *GUIDE):
        out.write(f"# {line}\n")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for name in names:
        repo = repositories[name]
        snapshot = repo.get("snapshot") or {}
        writer.writerow(
            [
                # A GitHub full name starts with a letter or digit; kept as-is so that
                # import_sheet matches it.
                name,
                f"https://github.com/{name}",
                _cell(repo.get("description", "")),
                _cell(_languages(repo.get("languages", []))),
                _cell("; ".join(repo.get("topics", []))),
                "; ".join(text for flag, text in CONTRIBUTION_FLAGS if repo.get(flag)),
                _cell(snapshot.get("activity_label", "")),
                len(repo.get("issues", [])),
                "",
                "",
            ]
        )
    return out.getvalue()


def read_sheet(text: str) -> dict[str, str]:
    """``{repository: grade text}`` from a filled sheet. Guide lines (``#``) are recognized only
    before the header; the rest is one CSV stream, so quoted multi-line fields stay whole.
    All-blank rows are skipped. Raises ``SheetError`` naming the row for a repeated repository
    or a grade or note without a repository."""
    lines = text.lstrip("﻿").splitlines(keepends=True)
    start = 0
    while start < len(lines) and (lines[start].startswith("#") or not lines[start].strip()):
        start += 1
    reader = csv.DictReader(io.StringIO("".join(lines[start:])))
    if reader.fieldnames is None or not {"repository", "grade"} <= set(reader.fieldnames):
        raise SheetError("The sheet needs a header with at least repository and grade columns.")
    grades: dict[str, str] = {}
    for row in reader:
        cells = {key: (value or "").strip() for key, value in row.items() if key is not None}
        if not any(cells.values()):
            continue
        line = start + reader.line_num
        name = cells.get("repository", "")
        if not name:
            if cells.get("grade") or cells.get("note"):
                raise SheetError(f"Row {line}: a grade or note without a repository.")
            continue
        if name in grades:
            raise SheetError(f"Row {line}: {name} is listed more than once.")
        grades[name] = cells.get("grade", "")
    return grades


def import_sheet(export: Mapping[str, Any], grades: Mapping[str, str]) -> dict[str, Any]:
    """A copy of ``export`` with the sheet's grades as judgments and the developer marked
    ``real``. Validates everything before returning; raises ``SheetError`` naming the row."""
    developer = dict(_single_developer(export))
    result: dict[str, Any] = {**export, "developers": [developer]}
    pool = set(_candidate_names(developer))
    judgments: dict[str, int] = {}
    for name, text in grades.items():
        if name not in pool:
            raise SheetError(f"Row {name}: not a candidate of this export.")
        if text == "":
            continue
        if text not in {str(g) for g in GRADES}:
            raise SheetError(f"Row {name}: grade must be 0, 1, 2 or blank, got {text!r}.")
        judgments[name] = int(text)
    if not any(grade >= 1 for grade in judgments.values()):
        raise SheetError("No row is graded 1 or 2.")
    developer["judgments"] = judgments
    developer["kind"] = REAL
    developer["description"] = JUDGED
    result["description"] = JUDGED
    try:
        parse(result)
    except DatasetError as exc:
        raise SheetError(str(exc)) from exc
    return result
