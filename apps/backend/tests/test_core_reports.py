import json
from pathlib import Path

import pytest
from django.core.management.base import CommandError

from core.reports import json_text, write_json


def test_json_text_keeps_non_ascii_and_ends_with_a_newline() -> None:
    text = json_text({"description": "日本語 café"})
    assert "日本語 café" in text
    assert text.endswith("}\n")
    assert json.loads(text) == {"description": "日本語 café"}


def test_write_json_creates_folders_and_writes_utf8(tmp_path: Path) -> None:
    out = tmp_path / "a" / "b" / "report.json"
    write_json(out, {"name": "Zoë", "values": [1, 2]}, what="Report")
    raw = out.read_bytes()
    assert "Zoë".encode() in raw
    assert raw.endswith(b"\n")
    assert json.loads(raw.decode("utf-8")) == {"name": "Zoë", "values": [1, 2]}


def test_write_json_failure_names_the_file(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    out = blocker / "report.json"  # its parent is a file
    with pytest.raises(CommandError, match=r"^Benchmark not written to .*report\.json: "):
        write_json(out, {}, what="Benchmark")
