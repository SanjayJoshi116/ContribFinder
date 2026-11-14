from argparse import ArgumentParser
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.reports import write_json
from services.discovery import yield_report
from services.discovery.yield_report import YieldReport, YieldRow

COLUMNS = ("requests", "refused", "results", "per req", "recorded", "share")


class Command(BaseCommand):
    help = (
        "Report how discovery's search requests were spent, per strategy and star band, from "
        "finished discovery runs. Aggregates only; changes no stored data."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--since", type=int, metavar="DAYS", help="Default: all time.")
        parser.add_argument("--json", metavar="OUT", help="Also write the report here.")

    def handle(self, *args: Any, **options: Any) -> None:
        since_days = options["since"]
        if since_days is not None and since_days < 1:
            raise CommandError("--since must be at least 1 day.")
        since = timezone.now() - timedelta(days=since_days) if since_days else None
        report = yield_report.build(yield_report.load(since), since_days=since_days)
        self._print(report)
        if options["json"]:
            out = options["json"]
            write_json(out, report.as_dict(), what="Report")
            self.stdout.write(f"Report written to {out}")

    def _print(self, report: YieldReport) -> None:
        window = f"last {report.since_days} days" if report.since_days else "all time"
        self.stdout.write(
            f"Discovery search yield, {window}: {report.runs} finished runs, "
            f"{report.runs_without_search} without a search, "
            f"{report.runs_without_yield} without per-query yield (neither in any figure)"
        )
        if report.total.requests == 0:
            self.stdout.write("No recorded search requests.")
            return
        self._table("total", [report.total])
        self._table("strategy", list(report.strategies))
        self._table("band", list(report.bands))
        self._table("strategy and band", list(report.strategy_bands))
        self.stdout.write(
            "\nper req = results per request that ran; share = results recorded as candidates "
            "(after pre-filtering and the not_code check). A repository found by two queries "
            "counts for both."
        )

    def _table(self, title: str, rows: list[YieldRow]) -> None:
        width = max(len(title), *(len(row.name) for row in rows))
        header = "  ".join(f"{c:>8}" for c in COLUMNS)
        self.stdout.write(f"\n{title:<{width}}  {header}  rejections")
        for row in rows:
            values = (
                row.requests,
                row.refused,
                row.results,
                _number(row.results_per_request, 1),
                row.recorded,
                _number(row.recorded_share, 4),
            )
            cells = "  ".join(f"{v:>8}" for v in values)
            listed = ", ".join(f"{reason} {n}" for reason, n in row.rejections.items()) or "-"
            self.stdout.write(f"{row.name:<{width}}  {cells}  {listed}")


def _number(value: float | None, places: int) -> str:
    return "-" if value is None else f"{value:.{places}f}"
