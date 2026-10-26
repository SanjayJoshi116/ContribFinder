from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from services.ranking import activation


class Command(BaseCommand):
    help = (
        "Activate a stored scoring configuration. Refused unless it is an improvement over the "
        "active one on the selection benchmark; --force with --reason overrides that. Audited."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("version", help="Stored configuration version, e.g. v2-deterministic.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Activate even when it is not an improvement (e.g. a rollback). Needs --reason.",
        )
        parser.add_argument("--reason", default="", help="Why; recorded in the audit log.")

    def handle(self, *args: Any, **options: Any) -> None:
        version = options["version"]
        try:
            result = activation.activate(version, force=options["force"], reason=options["reason"])
        except activation.ActivationRefused as refused:
            self.stdout.write(f"{version}: not an improvement over the active configuration")
            for failure in refused.failures:
                self.stdout.write(f"  - {failure}")
            raise CommandError(
                f"{version} was not activated. Use --force --reason for a deliberate exception."
            ) from refused
        except activation.ActivationError as exc:
            raise CommandError(str(exc)) from exc

        if not result.changed:
            self.stdout.write(f"{version} is already active; nothing changed.")
            return
        for failure in result.failures:
            self.stdout.write(f"  - {failure}")
        forced = " (forced)" if result.forced else ""
        previous = f", replacing {result.previous}" if result.previous else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{version} is active{forced}{previous}; recommendations regenerate on the next "
                "freshness run."
            )
        )
