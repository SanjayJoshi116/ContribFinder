import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from recommendations.models import ScoringConfig
from services.evaluation import baseline
from services.evaluation.dataset import DEFAULT_DATASET, DatasetError, load
from services.evaluation.metrics import METRICS
from services.evaluation.runner import (
    DEFAULT_TOLERANCE,
    ConfigError,
    ConfigSpec,
    Report,
    active_config,
    compare,
    evaluate,
    file_config,
    stored_config,
)


class Command(BaseCommand):
    help = (
        "Evaluate scoring configurations on a benchmark dataset (Precision@5/10, Recall@10, "
        "MRR, NDCG@10). The first configuration is the baseline. Changes no stored data."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--config",
            action="append",
            default=[],
            metavar="VERSION",
            help="Stored configuration version (repeatable). Default: the active one.",
        )
        parser.add_argument(
            "--config-file",
            action="append",
            default=[],
            metavar="PATH",
            help="Unsaved configuration: JSON with weights and params (repeatable). "
            "Evaluated after the stored versions.",
        )
        parser.add_argument("--dataset", default=str(DEFAULT_DATASET), metavar="PATH")
        parser.add_argument("--json", metavar="OUT", help="Also write the full report here.")
        parser.add_argument(
            "--require-improvement",
            action="store_true",
            help="Exit non-zero unless every configuration after the first improves on it.",
        )
        parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
        parser.add_argument("--min-score", type=float, help="Default: RECOMMENDATION_MIN_SCORE.")
        parser.add_argument("--top-n", type=int, help="Default: RECOMMENDATIONS_TOP_N.")
        parser.add_argument(
            "--write-baseline",
            action="store_true",
            help="Rewrite evaluation/baselines.json from the stored configurations (all of "
            "them unless --config is given), with the pinned min score and top N.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            dataset = load(options["dataset"])
            specs = self._specs(options)
        except (DatasetError, ConfigError) as exc:
            raise CommandError(str(exc)) from exc
        pinned = options["write_baseline"]
        min_score = options["min_score"]
        if min_score is None:
            min_score = baseline.MIN_SCORE if pinned else settings.RECOMMENDATION_MIN_SCORE
        top_n = options["top_n"] or (baseline.TOP_N if pinned else settings.RECOMMENDATIONS_TOP_N)

        reports = [evaluate(dataset, spec, min_score=min_score, top_n=top_n) for spec in specs]
        self._print(dataset.name, len(dataset.developers), reports)

        if options["json"]:
            Path(options["json"]).write_text(
                json.dumps({"reports": [r.as_dict() for r in reports]}, indent=2) + "\n",
                encoding="utf-8",
            )
            self.stdout.write(f"Report written to {options['json']}")
        if options["write_baseline"]:
            baseline.write(reports)
            self.stdout.write(f"Baseline written to {baseline.BASELINES}")

        verdicts = compare(reports[0], reports[1:], options["tolerance"])
        for verdict in verdicts:
            if verdict.improvement:
                self.stdout.write(f"{verdict.config}: improvement over {reports[0].config}")
            else:
                self.stdout.write(f"{verdict.config}: not an improvement over {reports[0].config}")
                for failure in verdict.failures:
                    self.stdout.write(f"  - {failure}")
        if options["require_improvement"]:
            if not verdicts:
                raise CommandError("--require-improvement needs at least two configurations.")
            if not all(v.improvement for v in verdicts):
                raise CommandError("Not every configuration improves on the baseline.")

    def _specs(self, options: dict[str, Any]) -> list[ConfigSpec]:
        versions: list[str] = options["config"]
        if options["write_baseline"] and options["config_file"]:
            raise ConfigError("--write-baseline records stored configurations only.")
        if options["write_baseline"] and not versions:
            versions = list(
                ScoringConfig.objects.order_by("created_at", "pk").values_list("version", flat=True)
            )
        specs = [stored_config(v) for v in versions]
        specs += [file_config(p) for p in options["config_file"]]
        return specs or [active_config()]

    def _print(self, dataset: str, developers: int, reports: list[Report]) -> None:
        first = reports[0]
        self.stdout.write(
            f"Dataset {dataset}: {developers} developers; "
            f"min score {first.min_score}, top N {first.top_n}\n"
        )
        width = max(len(r.config) for r in reports)
        self.stdout.write(f"{'config':<{width}}  " + "  ".join(f"{m:>17}" for m in METRICS))
        for report in reports:
            cells = []
            for name in METRICS:
                value = report.metrics[name]
                if report is first:
                    cells.append(f"{value:>17.4f}")
                else:
                    delta = value - first.metrics[name]
                    cells.append(f"{value:.4f} ({delta:+.4f})".rjust(17))
            self.stdout.write(f"{report.config:<{width}}  " + "  ".join(cells))

        for index, dev in enumerate(first.developers):
            self.stdout.write(f"\n{dev.id}")
            for report in reports:
                result = report.developers[index]
                values = "  ".join(f"{m} {result.metrics[m]:.4f}" for m in METRICS)
                self.stdout.write(
                    f"  {report.config}: {values}  unjudged {result.unjudged}  "
                    f"ranked {result.ranked}"
                )
                for rank, (name, grade) in enumerate(result.top, start=1):
                    shown = "?" if grade is None else str(grade)
                    self.stdout.write(f"    {rank:>2}. {name} [{shown}]")
