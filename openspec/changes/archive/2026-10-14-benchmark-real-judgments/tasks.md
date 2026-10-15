## 1. Dataset kind and subsets (spec: "Benchmark dataset", "Persona and real subsets"; design D4)

- [x] 1.1 `kind` (`persona` default | `real`) in dataset parsing, validation and `BenchmarkDeveloper`
- [x] 1.2 `Report.subsets` (means per kind when both present); `evaluate_ranking` prints persona and real rows; JSON report includes them
- [x] 1.3 Tests: kind default and validation; subsets present only for mixed datasets; values are the per-kind means

## 2. Judging sheet and import (spec: "Blind judging sheet", "Importing judgments"; design D1, D2)

- [x] 2.1 `services/evaluation/sheet.py`: write sheet (guide lines, columns, alphabetical, BOM) and read it back
- [x] 2.2 Commands `benchmark_sheet --export --out` and `import_judgments --export --sheet [--out]`
- [x] 2.3 Tests: blindness (no score/rank/label/reason/profile columns or values), alphabetical order, round-trip; import of valid sheet sets kind `real` and passes validation; unknown repository, invalid grade, no relevant grade each fail without writing

## 3. Build and selection (spec: "Benchmark with real developers", "Evaluation command", "Replacing the active configuration"; design D3, D5)

- [x] 3.1 `services/evaluation/build.py` and `build_benchmark` command (`--input` repeatable, `--on-conflict error|first`, validation before writing)
- [x] 3.2 `selection_dataset()`; `evaluate_ranking` default dataset uses it
- [x] 3.3 Tests: build of two inputs; duplicate developer id; conflicting repository fails / first wins with option; selection falls back to `benchmark-v1` without a real developer

## 4. Baseline format 3 (spec: "Regression baseline"; design D6)

- [x] 4.1 `baseline` format 3 keyed by dataset; `--write-baseline` updates only the evaluated dataset; `entries` reads formats 1–3
- [x] 4.2 Regression test iterates over the datasets present on disk; regenerate `baselines.json` (benchmark-v1 values unchanged)

## 5. Real judgments (human step; design D7)

- [x] 5.1 Document the export procedure in README (pool settings, refresh, export, sheet, import, build; consent; files in the gitignored `judging/` folder)
- [x] 5.2 (you) Raise the local pool, refresh, export your own account as `real-a`, write its sheet (39 candidates, `judging/real-a.json` and `.csv`)
- [~] 5.3 (you) Judge `real-a` (every row if possible); export and judge further consenting developers (`real-b`, ...) if available
- [~] 5.4 Import judgments; build `benchmark-v2` from `benchmark-v1` and the judged exports; decide (you) whether to commit `benchmark-v2.json`
- [~] 5.5 Evaluate v1 and v2 on `benchmark-v2` (all / persona / real); `--write-baseline` for `benchmark-v2`; record the numbers for the CHANGELOG (report only, no selection)

Carried over (5.3-5.5): 3 of 39 `real-a` rows graded when archived; the pool is almost all very large projects (median 906 contributors), a discovery bias to fix first. `benchmark-v2` was not built.

## 6. Verification, docs and release

- [x] 6.1 Backend checks: `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`; schema export has no drift
- [x] 6.2 Docs: README (judging workflow, selection benchmark), CLAUDE.md (layout, commands, selection benchmark)
- [x] 6.3 Release housekeeping per CLAUDE.md §8 at archive time (v0.11.0): versions and lockfiles, CHANGELOG (v1/v2 on benchmark-v2 incl. real subset), features.txt, README status, CLAUDE.md
