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


class SheetError(Exception):
    pass


def _single_developer(export: Mapping[str, Any]) -> dict[str, Any]:
    developers = export.get("developers")
    if not isinstance(developers, list) or len(developers) != 1:
        raise SheetError("An export must hold exactly one developer.")
    developer: dict[str, Any] = developers[0]
    return developer


def _languages(pairs: list[list[Any]]) -> str:
    total = sum(size for _, size in pairs) or 1
    top = sorted(pairs, key=lambda p: (-p[1], p[0]))[:3]
    return "; ".join(f"{name} {round(100 * size / total)}%" for name, size in top)


def write_sheet(export: Mapping[str, Any]) -> str:
    """The sheet as CSV text; write it with ``encoding="utf-8-sig"`` (BOM for spreadsheets)."""
    developer = _single_developer(export)
    repositories = export.get("repositories", {})
    out = io.StringIO()
    for line in (f"developer: {developer.get('id', '')}", *GUIDE):
        out.write(f"# {line}\n")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    names = sorted(c["repository"] for c in developer.get("candidates", []))
    for name in names:
        repo = repositories[name]
        snapshot = repo.get("snapshot") or {}
        writer.writerow(
            [
                name,
                f"https://github.com/{name}",
                repo.get("description", ""),
                _languages(repo.get("languages", [])),
                "; ".join(repo.get("topics", [])),
                "; ".join(text for flag, text in CONTRIBUTION_FLAGS if repo.get(flag)),
                snapshot.get("activity_label", ""),
                len(repo.get("issues", [])),
                "",
                "",
            ]
        )
    return out.getvalue()


def read_sheet(text: str) -> dict[str, str]:
    """``{repository: grade text}`` from a filled sheet (guide lines skipped)."""
    lines = [line for line in text.lstrip("﻿").splitlines() if not line.startswith("#")]
    reader = csv.DictReader(lines)
    if reader.fieldnames is None or not {"repository", "grade"} <= set(reader.fieldnames):
        raise SheetError("The sheet needs a header with at least repository and grade columns.")
    return {row["repository"].strip(): (row.get("grade") or "").strip() for row in reader}


def import_sheet(export: Mapping[str, Any], grades: Mapping[str, str]) -> dict[str, Any]:
    """A copy of ``export`` with the sheet's grades as judgments and the developer marked
    ``real``. Validates everything before returning; raises ``SheetError`` naming the row."""
    result: dict[str, Any] = {**export, "developers": [dict(_single_developer(export))]}
    developer = result["developers"][0]
    pool = {c["repository"] for c in developer.get("candidates", [])}
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
    try:
        parse(result)
    except DatasetError as exc:
        raise SheetError(str(exc)) from exc
    return result
