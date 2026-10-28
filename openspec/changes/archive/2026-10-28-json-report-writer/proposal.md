## Why

Seven management commands copy the same "write a JSON file" block: create the parent folder,
`json.dumps(..., indent=2)`, write UTF-8, turn `OSError` into `CommandError` (`Bug_Backlog.md`
T-14, accepted; `ideas.md` §15). The copies have already drifted: three keep non-ASCII text
as-is and four escape it, `e2e_seed` has no error handling and no trailing newline, and each
words its error differently. A new report command would copy one of them again.

## What Changes

- One helper, `core/reports.py`: `json_text(data)` (indent 2, non-ASCII kept, trailing newline)
  and `write_json(out, data, *, what)` (creates the folder, writes UTF-8, raises
  `CommandError("<what> not written to <out>: <reason>")` on `OSError`).
- `evaluate_ranking`, `feedback_report`, `discovery_report`, `export_benchmark_developer`,
  `import_judgments`, `build_benchmark` and `e2e_seed` use it; `export_benchmark_developer`
  prints `json_text` to stdout when no `--out` is given.
- Visible differences, all in output files and error text, none in data: every JSON file keeps
  non-ASCII characters unescaped and ends with a newline; `e2e_seed` reports a write failure as
  a command error instead of a traceback; error messages share one wording.
- Not in scope: `benchmark_sheet` (writes CSV with a BOM for spreadsheet tools) and
  `baselines.json` (written by `services/evaluation/baseline.py`, with its own merge rules).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

(none: no spec-level behavior changes; `skip_specs: true`)

## Impact

- New `apps/backend/core/reports.py` and its tests.
- Seven management commands (`recommendations/`, `repositories/`, `e2e/`).
- `Bug_Backlog.md` T-14, `ideas.md` §15 (moved to Shipped), `CLAUDE.md` §4 (core layout) and §7,
  `features.txt`, `CHANGELOG.md`.
- No API, model, migration or ranking change; baselines unchanged.
