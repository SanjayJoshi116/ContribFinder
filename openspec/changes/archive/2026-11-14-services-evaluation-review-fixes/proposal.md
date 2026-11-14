## Why

Review sweep of `apps/backend/services/evaluation/` (dataset, metrics, runner, bootstrap,
baseline, export, sheet, build, feedback report). `/code-review` reported 10 findings, each
checked against the code and the specs (EVL-1…EVL-10 in `Bug_Backlog.md`, batch 64).
`/security-review` reported one candidate, formula injection in the judging CSV. Its
false-positive check rated it 3/10 (only the owner opens the sheet, it holds no secret, and
spreadsheets prompt before fetching external data), so it is not a vulnerability. The
same finding came from `/code-review` as EVL-6 and is fixed here as hardening.

The ones that matter: the feedback report counts every event, so repeated opens and undone saves
inflate a configuration's shares (EVL-3); the bootstrap marks differences on 4-developer
holdouts that no test at 95% could support (EVL-1); and `--write-baseline` writes the committed
`baselines.json` non-atomically and can record datasets the baseline test never checks (EVL-4,
EVL-5).

## What Changes

- **EVL-1** A bootstrap difference is marked only when the dataset holds at least 6 developers,
  the fewest for which an exact two-sided sign test can reach 5%. With fewer, the report says the
  difference is not marked because there are too few developers. Intervals are unchanged.
- **EVL-2** The position-adjusted share also reports its coverage: the share of the common
  bucket weight that the configuration's shared buckets carry. Two adjusted shares are
  comparable only at similar coverage.
- **EVL-3** Shares count outcomes, not events. Each user, repository and configuration version
  has one outcome: its latest decisive event that was not undone. `unsaved` undoes the latest
  save before it and `undismissed` the latest dismissal. The outcome's rank bucket and match
  label come from that event. Action counts stay raw event counts.
- **EVL-4** `baseline.write` writes through `core.reports.write_json` (atomic; an OS error is a
  command error, not a traceback).
- **EVL-5** `--write-baseline` refuses a dataset unless it is the file
  `evaluation/<name>.json` of its own name, because that is the only place the baseline test
  and the default rewrite look.
- **EVL-6** Judging-sheet cells that start with `=`, `+`, `-`, `@`, a tab or a carriage return
  are written with a leading `'`. Import reads only repository and grade, so it is unaffected.
- **EVL-7** Dismiss reasons and match labels outside the current choices are reported after the
  known ones instead of disappearing. Calibration still uses the known labels only.
- **EVL-8** Accepted, no change: the draws are already made once per comparison. With at most
  6 developers that is 60,000 integers, which is negligible.
- **EVL-9** Dataset validation rejects an issue `updated_at` without a UTC offset. Every
  committed dataset already has one, so the baselines do not move.
- **EVL-10** `build` and `write_sheet` reject badly shaped input (repositories not an object, a
  developer not an object, a candidate missing from the catalog) with `BuildError` /
  `SheetError`. `resolved` lists each repository once.

No ranking change: `baselines.json` must not move (EVL-4 rewrites the same bytes).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `recommendation-evaluation`: "Dataset validation" (EVL-9), "Uncertainty of a comparison"
  (EVL-1), "Feedback report" (EVL-2, EVL-3, EVL-7), "Regression baseline" (EVL-5), "Blind
  judging sheet" (EVL-6, EVL-10), "Benchmark with real developers" (EVL-10).

## Impact

- Code: `services/evaluation/bootstrap.py`, `runner.py`, `baseline.py`, `dataset.py`,
  `sheet.py`, `build.py`, `feedback_report.py`; commands `evaluate_ranking` (marks, dataset
  check) and `feedback_report` (coverage column, outcome counts).
- Tests: bootstrap, runner, baseline, dataset, sheet, build, feedback report and the two
  commands.
- No API, migration, OpenAPI or frontend change. Patch release after `ranking-review-fixes`
  (0.12.67 if that ships as 0.12.66).
