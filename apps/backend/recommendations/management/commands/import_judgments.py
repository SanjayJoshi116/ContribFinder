import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from services.evaluation.sheet import SheetError, import_sheet, read_sheet


class Command(BaseCommand):
    help = (
        "Read a filled judging sheet back into its export: grades become judgments and the "
        "developer is marked real. Nothing is written unless the whole sheet is valid."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--export", required=True, metavar="PATH")
        parser.add_argument("--sheet", required=True, metavar="PATH")
        parser.add_argument("--out", metavar="PATH", help="Default: update the export in place.")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            export = json.loads(Path(options["export"]).read_text(encoding="utf-8"))
            grades = read_sheet(Path(options["sheet"]).read_text(encoding="utf-8-sig"))
            judged = import_sheet(export, grades)
        except (OSError, ValueError, SheetError) as exc:
            raise CommandError(f"Judgments not imported: {exc}") from exc
        out = Path(options["out"] or options["export"])
        text = json.dumps(judged, indent=2, ensure_ascii=False) + "\n"
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
        except OSError as exc:
            raise CommandError(f"Judgments not written: {exc}") from exc
        judgments = judged["developers"][0]["judgments"]
        candidates = len(judged["developers"][0]["candidates"])
        self.stdout.write(
            f"Imported {len(judgments)} of {candidates} judgments "
            f"({sum(1 for g in judgments.values() if g >= 1)} relevant) into {out}."
        )
