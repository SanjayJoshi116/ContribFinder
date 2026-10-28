import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.reports import write_json
from services.evaluation.build import ERROR, ON_CONFLICT, BuildError, build


class Command(BaseCommand):
    help = (
        "Build a benchmark dataset from datasets and judged exports (e.g. benchmark-v1 plus real "
        "developers). Validated before writing."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--name", required=True, help="Dataset name, e.g. benchmark-v2.")
        parser.add_argument("--out", required=True, metavar="PATH")
        parser.add_argument(
            "--input", action="append", required=True, metavar="PATH", help="Repeatable, in order."
        )
        parser.add_argument("--description", default="")
        parser.add_argument("--on-conflict", choices=ON_CONFLICT, default=ERROR)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            inputs = [
                (path, json.loads(Path(path).read_text(encoding="utf-8")))
                for path in options["input"]
            ]
            result, resolved = build(
                options["name"], options["description"], inputs, options["on_conflict"]
            )
        except (OSError, ValueError, BuildError) as exc:
            raise CommandError(f"Benchmark not built: {exc}") from exc
        write_json(options["out"], result, what="Benchmark")
        kinds: dict[str, int] = {}
        for developer in result["developers"]:
            kind = developer.get("kind", "persona")
            kinds[kind] = kinds.get(kind, 0) + 1
        summary = ", ".join(f"{n} {kind}" for kind, n in sorted(kinds.items()))
        self.stdout.write(
            f"Built {options['name']}: {summary} developers, "
            f"{len(result['repositories'])} repositories -> {options['out']}"
        )
        for name in resolved:
            self.stdout.write(f"  kept the first entry of {name} (inputs differed)")
