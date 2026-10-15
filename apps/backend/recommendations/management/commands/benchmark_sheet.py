import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from services.evaluation.sheet import SheetError, write_sheet


class Command(BaseCommand):
    help = (
        "Write a blind judging sheet (CSV) for an exported benchmark developer: the facts a "
        "contributor would look at, alphabetically, with no score, rank, label or reason."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--export", required=True, metavar="PATH", help="Exported developer.")
        parser.add_argument("--out", required=True, metavar="PATH", help="Sheet to write (CSV).")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            export = json.loads(Path(options["export"]).read_text(encoding="utf-8"))
            text = write_sheet(export)
            out = Path(options["out"])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8-sig")
        except (OSError, ValueError, KeyError, SheetError) as exc:
            raise CommandError(f"Cannot write a sheet: {exc}") from exc
        rows = len(export["developers"][0]["candidates"])
        self.stdout.write(
            f"Sheet with {rows} rows written to {options['out']}. Fill the grade column, then "
            "run import_judgments."
        )
