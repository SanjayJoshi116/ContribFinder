## 1. Baseline file (format 4)

- [x] 1.1 `services/evaluation/baseline.py`: format 4 (`top_n` per dataset), `top_n(data, dataset)` reading formats 1–4, `BaselineError` (D2)
- [x] 1.2 `baseline.write`: group reports by dataset, merge evaluated configs into the recorded entry, keep other configs and datasets; refuse a different top N unless every recorded config is covered; validate everything before the single write (D3)
- [x] 1.3 `test_baseline_metrics_unchanged` uses the per-dataset top N; extend `test_baseline_formats` for format 4 and the format 3 fallback
- [x] 1.4 Tests: merge keeps v1 when only v2 is written (E-1); different top N for part of a dataset fails with the file unchanged (R-2)

## 2. evaluate_ranking

- [x] 2.1 `--write-baseline` without `--dataset` evaluates `benchmark-v1`, recorded datasets with files, and the selection dataset (deduplicated), printing each report; `--require-improvement` covers every dataset (D1, R-1)
- [x] 2.2 Reject `--min-score` with `--write-baseline` before evaluating (D4, E-2)
- [x] 2.3 `--json`: create the parent folder; `OSError` → `CommandError` naming the path (D8, E-8)
- [x] 2.4 Tests: default write covers v1 and a present selection benchmark (temporary datasets dir); min-score refused with no write; JSON into a new folder; unwritable JSON path is a `CommandError`

## 3. Judging sheets

- [x] 3.1 `read_sheet`: guide lines only before the header, parse the rest as one CSV stream, skip all-blank rows, fail on duplicates and on grade/note without repository naming the row (D5, R-7, R-8)
- [x] 3.2 `import_sheet`: replace developer and export descriptions with the judged text (D6, R-14)
- [x] 3.3 `_languages`: `None` byte counts count as 0; names without shares when no counts (D9, E-9)
- [x] 3.4 Tests: `#` line in a quoted multi-line description; trailing blank rows; repeated repository; grade without repository; judged description; sheet for an export with `null` byte counts

## 4. build_benchmark

- [x] 4.1 `build`: each input must be an object with the current format, else `BuildError` naming the input (D7, R-13)
- [x] 4.2 Tests: a list input and a different-format input fail naming the input, no file written

## 5. Data, docs and checks

- [x] 5.1 Rewrite `evaluation/baselines.json` with `evaluate_ranking --write-baseline`; confirm the metrics are identical (only structure changes)
- [x] 5.2 README ("Evaluating a ranking change", "Judging real developers") and CLAUDE.md §6: default baseline datasets, merge, no `--min-score` with `--write-baseline`
- [x] 5.3 Mark R-1, R-2, E-1, E-2, R-7, R-8, R-13, R-14, E-8, E-9 `fixed (evaluation-tooling-integrity)` in `Bug_Backlog.md`
- [x] 5.4 Backend checks: pytest, ruff check/format, mypy; `openspec validate evaluation-tooling-integrity --strict`
