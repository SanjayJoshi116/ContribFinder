from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.reports import write_json
from recommendations.models import ScoringConfig
from services.evaluation import baseline, bootstrap
from services.evaluation.dataset import DatasetError, load, selection_dataset
from services.evaluation.metrics import METRICS
from services.evaluation.runner import (
    DEFAULT_TOLERANCE,
    ConfigError,
    ConfigSpec,
    Report,
    Verdict,
    active_config,
    compare,
    evaluate,
    file_config,
    stored_config,
    uncertainty,
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
        parser.add_argument(
            "--dataset",
            metavar="PATH",
            help="Default: the selection benchmark (benchmark-v2 once it holds a judged real "
            "developer, otherwise benchmark-v1).",
        )
        parser.add_argument("--json", metavar="OUT", help="Also write the full report here.")
        parser.add_argument(
            "--require-improvement",
            action="store_true",
            help="Exit non-zero unless every configuration after the first improves on it.",
        )
        parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
        parser.add_argument(
            "--min-score",
            type=float,
            help="Override every configuration's minimum score. Default: each configuration's "
            "own min_score, else RECOMMENDATION_MIN_SCORE.",
        )
        parser.add_argument("--top-n", type=int, help="Default: RECOMMENDATIONS_TOP_N.")
        parser.add_argument(
            "--resamples",
            type=int,
            default=bootstrap.DEFAULT_RESAMPLES,
            help="Bootstrap resamples for each comparison's interval.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=bootstrap.DEFAULT_SEED,
            help="Bootstrap seed; the same seed always gives the same intervals.",
        )
        parser.add_argument(
            "--write-baseline",
            action="store_true",
            help="Rewrite evaluation/baselines.json from the stored configurations (all of "
            "them unless --config is given), with the pinned min score and top N. Without "
            "--dataset: benchmark-v1, every recorded dataset and the selection benchmark. "
            "Configurations not evaluated keep their recorded values.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        pinned = options["write_baseline"]
        resamples, seed = options["resamples"], options["seed"]
        if resamples < 1:
            raise CommandError("--resamples must be at least 1.")
        if options["top_n"] is not None and options["top_n"] < 1:
            raise CommandError("--top-n must be at least 1.")
        try:
            if options["dataset"]:
                paths = [Path(options["dataset"])]
            elif pinned:
                paths = baseline.default_datasets()
            else:
                paths = [selection_dataset()]
            datasets = [load(path) for path in paths]
            specs = self._specs(options)
        except (DatasetError, ConfigError) as exc:
            raise CommandError(str(exc)) from exc
        override = options["min_score"] is not None
        min_score = options["min_score"]
        if min_score is None:
            min_score = baseline.MIN_SCORE if pinned else settings.RECOMMENDATION_MIN_SCORE
        top_n = options["top_n"]
        if top_n is None:
            top_n = baseline.TOP_N if pinned else settings.RECOMMENDATIONS_TOP_N

        everything: list[Report] = []
        verdicts: list[Verdict] = []
        comparisons: list[dict[str, Any]] = []
        for index, dataset in enumerate(datasets):
            if index:
                self.stdout.write("")
            reports = [
                evaluate(dataset, spec, min_score=min_score, top_n=top_n, override=override)
                for spec in specs
            ]
            self._print(dataset.name, len(dataset.developers), reports)
            found = compare(reports[0], reports[1:], options["tolerance"])
            prefix = f"{dataset.name}: " if len(datasets) > 1 else ""
            for verdict in found:
                result = "improvement" if verdict.improvement else "not an improvement"
                self.stdout.write(f"{prefix}{verdict.config}: {result} over {reports[0].config}")
                for failure in verdict.failures:
                    self.stdout.write(f"  - {failure}")
            for report in reports[1:]:
                intervals = uncertainty(reports[0], report, resamples=resamples, seed=seed)
                self._print_uncertainty(reports[0].config, report, intervals, resamples, seed)
                comparisons.append(
                    {
                        "dataset": dataset.name,
                        "baseline": reports[0].config,
                        "config": report.config,
                        "resamples": resamples,
                        "seed": seed,
                        "metrics": {name: i.as_dict() for name, i in intervals.items()},
                    }
                )
            everything += reports
            verdicts += found

        if options["json"]:
            out = options["json"]
            body = {"reports": [r.as_dict() for r in everything], "comparisons": comparisons}
            write_json(out, body, what="Report")
            self.stdout.write(f"Report written to {out}")
        if pinned:
            try:
                baseline.write(everything)
            except baseline.BaselineError as exc:
                raise CommandError(f"Baseline not written: {exc}") from exc
            self.stdout.write(
                f"Baseline written to {baseline.BASELINES} ({', '.join(d.name for d in datasets)})"
            )

        if options["require_improvement"]:
            if not verdicts:
                raise CommandError("--require-improvement needs at least two configurations.")
            if not all(v.improvement for v in verdicts):
                raise CommandError("Not every configuration improves on the baseline.")

    def _specs(self, options: dict[str, Any]) -> list[ConfigSpec]:
        versions: list[str] = options["config"]
        if options["write_baseline"] and options["config_file"]:
            raise ConfigError("--write-baseline records stored configurations only.")
        if options["write_baseline"] and options["min_score"] is not None:
            raise ConfigError(
                "--write-baseline records each configuration's own minimum score; "
                "--min-score cannot be used with it."
            )
        if options["write_baseline"] and not versions:
            versions = list(
                ScoringConfig.objects.order_by("created_at", "pk").values_list("version", flat=True)
            )
        specs = [stored_config(v) for v in versions]
        specs += [file_config(p) for p in options["config_file"]]
        return specs or [active_config()]

    def _print_uncertainty(
        self,
        baseline: str,
        report: Report,
        intervals: dict[str, bootstrap.Interval],
        resamples: int,
        seed: int,
    ) -> None:
        self.stdout.write(
            f"{report.config} vs {baseline} (paired bootstrap over developers, "
            f"{resamples} resamples, seed {seed})"
        )
        for name, i in intervals.items():
            mark = "  *" if i.marked else ""
            self.stdout.write(
                f"  {name:<13} {i.diff:+.4f}  [{i.low:+.4f}, {i.high:+.4f}]  "
                f"not better {i.not_better:6.1%}{mark}"
            )
        self.stdout.write("  * the 95% interval excludes 0; unmarked = inconclusive, not zero")

    def _print(self, dataset: str, developers: int, reports: list[Report]) -> None:
        first = reports[0]
        self.stdout.write(f"Dataset {dataset}: {developers} developers; top N {first.top_n}")
        for report in reports:
            source = "overridden" if report.min_score_overridden else "configuration or default"
            self.stdout.write(
                f"  {report.config}: min score {report.min_score} on {report.min_score_basis} "
                f"({source})"
            )
        self.stdout.write("")
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
            for kind, means in report.subsets.items():
                label = f"  {kind} only"
                subset = "  ".join(f"{means[name]:>17.4f}" for name in METRICS)
                self.stdout.write(f"{label:<{width}}  {subset}")

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
