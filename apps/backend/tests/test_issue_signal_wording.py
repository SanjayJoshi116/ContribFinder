"""The issue detail page words every difficulty signal the classifier writes (FI-2)."""

import re
from pathlib import Path

from django.conf import settings

from services.issues import classify

EVIDENCE_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "features" / "issues" / "evidence.ts"
)


def _worded_signals() -> set[str]:
    source = EVIDENCE_TS.read_text(encoding="utf-8")
    table = re.search(r"const SIGNAL_TEXT\b.*? = \{\n(.*?)\n\}", source, re.S)
    assert table, "SIGNAL_TEXT not found in evidence.ts"
    return set(re.findall(r"^  (\w+):", table.group(1), re.M))


def _written_signals() -> set[str]:
    _, evidence = classify.difficulty(
        raw_labels=["good first issue"],
        body="Fix the typo.",
        technology_count=1,
        contribution_type="documentation",
        comments=0,
        thresholds=settings.ISSUE_DIFFICULTY,
    )
    return {signal["signal"] for signal in evidence["signals"]}


def test_every_written_signal_has_words_on_the_issue_page() -> None:
    written = _written_signals()
    assert written
    assert _worded_signals() == written
