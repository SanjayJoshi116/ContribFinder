"""Blind judging sheets and judgment import (benchmark-real-judgments, group 2)."""

import json
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from services.evaluation.sheet import COLUMNS, SheetError, import_sheet, read_sheet, write_sheet

from .test_evaluation_dataset import minimal


def export() -> dict[str, Any]:
    """An unjudged one-developer export, as export_benchmark_developer writes it."""
    raw = minimal()
    raw["developers"][0]["judgments"] = {}
    return raw


def filled(text: str, grades: dict[str, str]) -> str:
    lines = []
    for line in text.splitlines():
        for name, grade in grades.items():
            if line.startswith(f"{name},"):
                line = line[: line.rindex(",,")] + f",{grade},"
        lines.append(line)
    return "\n".join(lines) + "\n"


def test_sheet_is_blind_and_alphabetical() -> None:
    text = write_sheet(export())
    rows = [line for line in text.splitlines() if not line.startswith("#")]
    assert rows[0] == ",".join(COLUMNS)
    assert [r.split(",")[0] for r in rows[1:]] == ["bench/django-kit", "bench/go-proxy"]
    lowered = text.lower()
    for word in ("score", "rank", "strong", "partial", "reason", "signal", "confidence"):
        assert word not in lowered
    for profile_value in ("0.9", "0.7", "intermediate", "web-development", "dev-a's"):
        assert profile_value not in rows[1] + rows[2]
    assert "Python 100%" in text and "CONTRIBUTING" in text and "recently_active" in text
    assert rows[1].endswith(",1,,")  # one eligible issue, empty grade and note


def test_round_trip_sets_judgments_and_kind() -> None:
    sheet = write_sheet(export())
    grades = read_sheet("﻿" + filled(sheet, {"bench/django-kit": "2"}))
    assert grades == {"bench/django-kit": "2", "bench/go-proxy": ""}
    judged = import_sheet(export(), grades)
    developer = judged["developers"][0]
    assert developer["judgments"] == {"bench/django-kit": 2} and developer["kind"] == "real"


@pytest.mark.parametrize(
    ("grades", "message"),
    [
        ({"bench/unknown": "1"}, "Row bench/unknown: not a candidate"),
        ({"bench/django-kit": "3"}, "grade must be 0, 1, 2 or blank, got '3'"),
        ({"bench/django-kit": "yes"}, "got 'yes'"),
        ({"bench/django-kit": "0", "bench/go-proxy": ""}, "No row is graded 1 or 2"),
    ],
)
def test_import_errors(grades: dict[str, str], message: str) -> None:
    with pytest.raises(SheetError, match=message):
        import_sheet(export(), grades)


def test_commands_write_nothing_on_error(tmp_path) -> None:
    exported = tmp_path / "real-a.json"
    exported.write_text(json.dumps(export()), encoding="utf-8")
    sheet = tmp_path / "judging" / "real-a.csv"  # folder created on write
    call_command(
        "benchmark_sheet", "--export", str(exported), "--out", str(sheet), stdout=StringIO()
    )
    assert sheet.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM for spreadsheet apps

    before = exported.read_text(encoding="utf-8")
    sheet.write_text(
        filled(sheet.read_text(encoding="utf-8-sig"), {"bench/django-kit": "5"}), encoding="utf-8"
    )
    with pytest.raises(CommandError, match="not imported"):
        call_command("import_judgments", "--export", str(exported), "--sheet", str(sheet))
    assert exported.read_text(encoding="utf-8") == before

    sheet.write_text(filled(write_sheet(export()), {"bench/django-kit": "1"}), encoding="utf-8")
    out = StringIO()
    call_command("import_judgments", "--export", str(exported), "--sheet", str(sheet), stdout=out)
    assert "Imported 1 of 2 judgments (1 relevant)" in out.getvalue()
    assert json.loads(exported.read_text(encoding="utf-8"))["developers"][0]["kind"] == "real"
