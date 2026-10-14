"""Evaluate the v3 candidates (design D4). Run from apps/backend:

    uv run python ../../openspec/changes/archive/2026-10-14-ranking-v3-deterministic/candidates/search.py benchmark
    uv run python ../../openspec/changes/archive/2026-10-14-ranking-v3-deterministic/candidates/search.py holdout c08

``benchmark`` evaluates every candidate on benchmark-v1 against v1 and v2 and prints the table
and the selection. ``holdout <id>`` evaluates the chosen candidate on holdout-v1 against v2;
``holdout all`` evaluates every candidate there, for the record only. Pinned min score and top N
as in baselines.json. Writes reports next to this file.
"""

import json
import os
import sys
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
sys.path.insert(0, os.getcwd())
django.setup()

from services.evaluation import baseline  # noqa: E402
from services.evaluation.dataset import DATASETS_DIR, DEFAULT_DATASET, load  # noqa: E402
from services.evaluation.metrics import METRICS  # noqa: E402
from services.evaluation.runner import compare, evaluate, file_config, stored_config  # noqa: E402

HERE = Path(__file__).resolve().parent
CANDIDATES = sorted(HERE.glob("c[0-9][0-9]-*.json"))


def run(dataset_path: Path, specs: list) -> list:
    dataset = load(dataset_path)
    return [
        evaluate(dataset, s, min_score=baseline.MIN_SCORE, top_n=baseline.TOP_N) for s in specs
    ]


def row(report, base=None) -> str:
    cells = []
    for m in METRICS:
        v = report.metrics[m]
        cells.append(f"{v:.4f}" if base is None else f"{v:.4f} ({v - base.metrics[m]:+.4f})")
    return f"| {Path(report.config).stem} | " + " | ".join(cells) + " |"


def header() -> str:
    return "| config | " + " | ".join(METRICS) + " |\n|---" * (len(METRICS) + 1) + "|"


def benchmark() -> None:
    v1, v2 = stored_config("v1-deterministic"), stored_config("v2-deterministic")
    reports = run(DEFAULT_DATASET, [v1, v2, *(file_config(p) for p in CANDIDATES)])
    r1, r2, rest = reports[0], reports[1], reports[2:]
    (HERE / "benchmark-report.json").write_text(
        json.dumps([r.as_dict() for r in reports], indent=2) + "\n", encoding="utf-8"
    )
    print(header())
    print(row(r1))
    print(row(r2, r1))
    qualified = []
    for report in rest:
        over_v1 = compare(r1, [report])[0]
        over_v2 = compare(r2, [report])[0]
        ok = over_v1.improvement and over_v2.improvement
        why = "" if ok else "; ".join(
            [f"vs v1: {f}" for f in over_v1.failures] + [f"vs v2: {f}" for f in over_v2.failures]
        )
        print(row(report, r2) + (" **qualifies**" if ok else f" fails: {why}"))
        if ok:
            qualified.append(report)

    def mechanisms(report) -> int:
        name = Path(report.config).stem
        return ("weighted" in name) + ("scaled" in name)

    qualified.sort(
        key=lambda r: (
            -r.metrics["ndcg@10"],
            -r.metrics["precision@5"],
            mechanisms(r),
            Path(r.config).stem,
        )
    )
    print("\nChosen:", Path(qualified[0].config).stem if qualified else "none qualifies")


def holdout(which: str) -> None:
    v2 = stored_config("v2-deterministic")
    paths = CANDIDATES if which == "all" else [p for p in CANDIDATES if p.stem.startswith(which)]
    reports = run(DATASETS_DIR / "holdout-v1.json", [v2, *(file_config(p) for p in paths)])
    name = "holdout-all-report.json" if which == "all" else f"holdout-{which}-report.json"
    (HERE / name).write_text(
        json.dumps([r.as_dict() for r in reports], indent=2) + "\n", encoding="utf-8"
    )
    print(header())
    print(row(reports[0]))
    for report in reports[1:]:
        drops = [
            f"{m} -{reports[0].metrics[m] - report.metrics[m]:.4f}"
            for m in METRICS
            if reports[0].metrics[m] - report.metrics[m] > 0.01
        ]
        print(row(report, reports[0]) + (f" regresses: {', '.join(drops)}" if drops else " ok"))


if __name__ == "__main__":
    if sys.argv[1] == "benchmark":
        benchmark()
    else:
        holdout(sys.argv[2])
