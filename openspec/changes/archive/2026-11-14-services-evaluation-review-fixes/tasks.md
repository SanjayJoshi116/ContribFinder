## 1. Benchmark comparison

- [x] 1.1 EVL-1: `MIN_MARKED_DEVELOPERS = 6`; `Interval.developers`; `marked` false below it; `as_dict` adds `developers`, `too_few`; command prints the too-few note (D1). Tests: 4 developers all better → interval above 0, not marked, `too_few`; 6 developers all better → marked; 1 developer → zero width, not marked.
- [x] 1.2 EVL-4: `baseline.write` through `core.reports.write_json` (D4). Tests: an unwritable path → `CommandError` from the command, file unchanged; rewriting the committed baselines with the same reports gives identical bytes.
- [x] 1.3 EVL-5: `--write-baseline` refuses a dataset that is not `evaluation/<name>.json`; `baseline.write` refuses a name without that file (D4). Tests: a copy of `benchmark-v1` under another path → command error, nothing written; a report for a dataset name with no file → `BaselineError`.

## 2. Dataset, sheet and build input

- [x] 2.1 EVL-9: issue `updated_at` needs a UTC offset (D5). Test: `"2026-09-20T12:00:00"` → `DatasetError` naming the developer, issue and field; committed datasets still load.
- [x] 2.2 EVL-6: `sheet._cell` prefixes `'` (D5). Tests: description `=HYPERLINK("x")` → cell `'=HYPERLINK("x")`; a normal description is unchanged; `read_sheet` → `import_sheet` round trip of such a sheet still imports the grades.
- [x] 2.3 EVL-10: shape errors in `build` and `write_sheet`; `resolved` once per repository (D5). Tests: `"repositories": []` → `BuildError`; a developer string → `BuildError`; a candidate missing from repositories → `SheetError`; three inputs conflicting on one repository with `--on-conflict first` → listed once.

## 3. Feedback report

- [x] 3.1 EVL-3: outcomes per (user, repository, version) from the latest non-undone decisive event; `load` reads `repository_full_name`, `created_at`, ordered; row `positive`/`decisive` fields from outcomes; counts stay raw (D3). Tests: one user opening a repo 6 times and dismissing 2 others → 1 positive of 3; save then unsave → no outcome; dismiss then undismiss then open → positive; the outcome's bucket is that of its event's rank; the spec scenarios still hold.
- [x] 3.2 EVL-2: `coverage` on `ConfigRows`, JSON and printed line (D2). Test: the position-adjustment scenario gives coverage 1.0 for both configurations; a configuration with a share only at ranks 1–5 gives the 1–5 weight share.
- [x] 3.3 EVL-7: unknown reasons and labels reported after the known ones (D6). Tests: a stored reason `not_interested` appears in the reasons line; a stored label `weak` gets a label row and does not change calibration.

## 4. Checks

- [x] 4.1 `test_baseline_metrics_unchanged` passes untouched; `baselines.json` unchanged.
- [x] 4.2 Backend: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`.

## 5. Release

- [x] 5.1 `Bug_Backlog.md` batch 64: EVL rows marked fixed (EVL-8 accepted).
- [x] 5.2 `/simplify`, then `/code-review` on the fix diff; record and fix (or skipped by the owner). Owner: marked done without a separate run.
- [x] 5.3 Archive (delta into `recommendation-evaluation`; `ranking-review-fixes` modifies a different requirement of the same spec, so archive in release order). Release housekeeping per CLAUDE.md §8 (CHANGELOG notes that feedback shares before and after are not comparable). Commit only when the owner says so.
