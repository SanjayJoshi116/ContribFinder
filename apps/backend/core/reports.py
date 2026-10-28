"""JSON files written by management commands: reports, exports, benchmarks, e2e sessions."""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import CommandError


def json_text(data: Any) -> str:
    """Indented JSON with non-ASCII text kept as-is and a trailing newline."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_json(out: Path | str, data: Any, *, what: str) -> None:
    """Write `data` to `out` as UTF-8, creating parent folders. `what` names the file in the
    error ("Report", "Benchmark", ...) when the write fails."""
    path = Path(out)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_text(data), encoding="utf-8")
    except OSError as exc:
        raise CommandError(f"{what} not written to {out}: {exc}") from exc
