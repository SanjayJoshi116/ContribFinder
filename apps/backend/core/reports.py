"""JSON files written by management commands: reports, exports, benchmarks, e2e sessions."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from django.core.management.base import CommandError


def json_text(data: Any) -> str:
    """Indented JSON with non-ASCII text kept as-is and a trailing newline."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_json(out: Path | str, data: Any, *, what: str) -> None:
    """Write `data` to `out` as UTF-8, creating parent folders. `what` names the file in the
    error ("Report", "Benchmark", ...) when the write fails. Serialized before any file is
    touched and written through a temporary file in the same folder, then swapped in: an
    interrupted write leaves the old file whole."""
    path = Path(out)
    try:
        text = json_text(data)
    except (TypeError, ValueError) as exc:
        raise CommandError(f"{what} not written to {out}: {exc}") from exc
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    except OSError as exc:
        raise CommandError(f"{what} not written to {out}: {exc}") from exc
