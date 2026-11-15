from argparse import ArgumentParser
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.reports import write_json
from services.evaluation import feedback_report
from services.evaluation.feedback_report import (
    ACTIONS,
    NOT_ORDERED,
    BucketRow,
    FeedbackReport,
    LabelRow,
    bucket_label,
)


class Command(BaseCommand):
    help = (
        "Report how users acted on recommendations, per scoring configuration and rank bucket, "
        "from stored feedback events. Aggregates only; changes no stored data."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--since", type=int, metavar="DAYS", help="Default: all time.")
        parser.add_argument(
            "--config",
            action="append",
            default=[],
            metavar="VERSION",
            help="Configuration version to include (repeatable). Default: every version.",
        )
        parser.add_argument(
            "--minimum",
            type=int,
            default=feedback_report.DEFAULT_MINIMUM,
            help="Decisive actions a group needs before its share is shown.",
        )
        parser.add_argument("--json", metavar="OUT", help="Also write the report here.")

    def handle(self, *args: Any, **options: Any) -> None:
        since_days = options["since"]
        if since_days is not None and since_days < 1:
            raise CommandError("--since must be at least 1 day.")
        if options["minimum"] < 1:
            raise CommandError("--minimum must be at least 1.")
        since = timezone.now() - timedelta(days=since_days) if since_days else None
        report = feedback_report.build(
            feedback_report.load(since),
            minimum=options["minimum"],
            since_days=since_days,
            versions=options["config"],
        )
        self._print(report)
        if options["json"]:
            out = options["json"]
            write_json(out, report.as_dict(), what="Report")
            self.stdout.write(f"Report written to {out}")

    def _print(self, report: FeedbackReport) -> None:
        window = f"last {report.since_days} days" if report.since_days else "all time"
        self.stdout.write(f"Feedback events, {window}; minimum {report.minimum} decisive actions")
        if not report.configs and not report.unattributed:
            self.stdout.write("No feedback events.")
            return
        for config in report.configs:
            self.stdout.write(f"\n{config.version}")
            self._table("ranks", [(bucket_label(row.bucket), row) for row in config.buckets])
            self.stdout.write(
                f"  positive share: raw {_share(config.raw_share)}, "
                f"position-adjusted {_share(config.adjusted_share)} "
                f"(coverage {_share(config.coverage)})"
            )
            if config.labels:
                self._table("label", [(row.label, row) for row in config.labels])
            found = config.calibration
            verdict = (
                f"{found.verdict} ({found.higher} below {found.lower})"
                if found.verdict == NOT_ORDERED
                else found.verdict
            )
            self.stdout.write(f"  calibration: {verdict}")
            if config.dismiss_reasons:
                self.stdout.write(f"  dismiss reasons: {_counts(config.dismiss_reasons)}")
        if report.unattributed:
            self.stdout.write(
                f"\nWithout a recommendation snapshot (in no share): {_counts(report.unattributed)}"
            )
            if report.unattributed_dismiss_reasons:
                listed = _counts(report.unattributed_dismiss_reasons)
                self.stdout.write(f"  dismiss reasons: {listed}")
        self.stdout.write(
            "\nShare = saved + opened (repository or issue) out of those plus dismissed, counting "
            "one outcome per user, repository and configuration (its latest decisive action not "
            "undone): a share of decisive outcomes, not of recommendations shown. Action counts "
            "are every event. '-' = below the minimum. Coverage = the part of the bucket weight "
            "behind the adjusted share; compare adjusted shares at similar coverage. Label "
            "shares are not adjusted for rank; read the calibration with the user counts."
        )

    def _table(self, title: str, rows: list[tuple[str, BucketRow | LabelRow]]) -> None:
        """Action counts, users and share per row; the first column names the row."""
        header = "  ".join(f"{a:>17}" for a in ACTIONS)
        self.stdout.write(f"  {title:<7} {header}  {'users':>5}  {'share':>6}")
        for name, row in rows:
            counts = "  ".join(f"{row.counts[a]:>17}" for a in ACTIONS)
            self.stdout.write(f"  {name:<7} {counts}  {row.users:>5}  {_share(row.share):>6}")


def _share(value: float | None) -> str:
    return "-" if value is None else f"{value:.4f}"


def _counts(found: dict[str, int]) -> str:
    return ", ".join(f"{name} {n}" for name, n in found.items())
