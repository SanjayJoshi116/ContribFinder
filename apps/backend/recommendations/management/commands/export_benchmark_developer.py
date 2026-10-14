import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from services.evaluation.export import NotAnalyzed, export_developer


class Command(BaseCommand):
    help = (
        "Export one user's stored developer features and candidate pool as an anonymized "
        "benchmark developer, without judgments (no GitHub requests). Review the file and add "
        "judgments by hand before committing it."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--user-id", type=int, required=True, help="User ID to export.")
        parser.add_argument(
            "--as", dest="developer_id", required=True, help="Benchmark developer id, e.g. dev-f."
        )
        parser.add_argument("--out", metavar="PATH", help="Output file. Default: stdout.")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            data = export_developer(options["user_id"], options["developer_id"], timezone.now())
        except NotAnalyzed as exc:
            raise CommandError(str(exc)) from exc
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if options["out"]:
            Path(options["out"]).write_text(text, encoding="utf-8")
            candidates = len(data["developers"][0]["candidates"])
            self.stdout.write(
                f"Exported {options['developer_id']} ({candidates} candidates) to "
                f"{options['out']}. Add judgments by hand."
            )
        else:
            self.stdout.write(text)
