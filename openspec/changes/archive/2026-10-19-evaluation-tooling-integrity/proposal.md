## Why

Judging the first real developer (`real-a-v2`, backlog K-1) feeds the regression baseline and the first selection benchmark with real judgments. Today the tooling on that path can silently write a baseline that CI then rejects, record wrong numbers, lose or misattribute grades from a spreadsheet, and crash with tracebacks on ordinary inputs (batch 3 of `Bug_Backlog.md`: R-1, R-2, E-1, E-2, R-7, R-8, R-13, R-14, E-8, E-9). It has to be trustworthy before anyone spends hours judging.

## What Changes

- `evaluate_ranking --write-baseline`:
  - With no `--dataset`, it rewrites every baseline dataset: `benchmark-v1`, any dataset already recorded whose file exists, and the selection benchmark. Today it writes only the selection benchmark, so the `benchmark-v1` entry that CI checks is never refreshed once `benchmark-v2` exists (R-1).
  - It merges into the dataset's entry instead of replacing it. Configurations that were not evaluated keep their recorded metrics, so `--config v2-deterministic` no longer drops v1 (E-1).
  - The baseline file records `top_n` per dataset (new format 4). A run at a different top N must cover every configuration recorded for that dataset, so recorded metrics never mix two top N values (R-2).
  - It refuses `--min-score`, since an overridden minimum score can never be reproduced by the baseline test (E-2).
- `evaluate_ranking --json` creates the output folder and reports a write failure as a command error, not a traceback (E-8).
- Judging sheet import:
  - Guide lines are skipped only before the header, so a `#` line inside a quoted multi-line description is kept (R-7).
  - Fully blank rows are ignored. A repeated repository, or a graded row with no repository, fails the import and names the row (R-8).
  - The imported developer's description says it was judged, replacing the export's "add judgments by hand" note (R-14).
- `benchmark_sheet` handles language byte counts the dataset format allows to be missing (`null`), instead of crashing (E-9).
- `build_benchmark` fails with a message naming the input when an input is not a dataset object or has a different format version, instead of a traceback (R-13).
- No ranking, API, model or UI change. The recorded metrics stay the same; `baselines.json` moves to format 4 with the same numbers.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-evaluation`: "Regression baseline" (which datasets are rewritten, merging, top N per dataset, no min-score override), "Evaluation command" (JSON output folder and write errors), "Blind judging sheet" (missing byte counts), "Importing judgments" (guide lines, blank and duplicate rows, judged description), "Benchmark with real developers" (invalid input files).

## Impact

- Backend only, offline commands:
  - `services/evaluation/baseline.py`, `sheet.py`, `build.py`;
  - commands `evaluate_ranking`, `import_judgments`, `build_benchmark`;
  - `evaluation/baselines.json`, rewritten to format 4 with unchanged metrics;
  - tests in `test_evaluation_benchmark.py` and `test_evaluation_commands.py`, plus the sheet and build tests.
- Docs: README "Evaluating a ranking change" and "Judging real developers", CLAUDE.md §6.
- Unblocks K-1 (judging `real-a-v2`).
