## Context

The seven blocks are listed in proposal.md. Commands are thin wrappers over `services/`
(CLAUDE.md §5); writing a file and mapping `OSError` to `CommandError` is command plumbing,
not business logic. `core/` already holds cross-app plumbing (`checks`, `startup`, `backoff`).

## Goals / Non-Goals

**Goals:**
- One place that decides how a command writes JSON and reports a failed write.
- No change to any file's data: only escaping and the trailing newline may differ.

**Non-Goals:**
- A common `--json` option or base command class: the commands' options differ (`--json`,
  `--out`, positional paths) and stay as they are.
- CSV output (`benchmark_sheet`) and `baselines.json`.

## Decisions

### D1. `core/reports.py`, two functions

`json_text(data) -> str` and `write_json(out, data, *, what) -> None`. `out` is a `Path` or a
string; `what` names the file in the error ("Report", "Benchmark", "Judgments", "Export",
"Sessions"). The message is `f"{what} not written to {out}: {exc}"`.
*Alternative:* `services/reports.py`. Rejected: services hold business logic and must not
import `django.core.management`; a helper that raises `CommandError` belongs next to commands.
*Alternative:* return the error and let each command raise. Rejected: every caller would raise
the same thing.

### D2. Non-ASCII kept everywhere (`ensure_ascii=False`)

The judging files (`import_judgments`, `build_benchmark`, `export_benchmark_developer`) already
keep it, so a repository description in Japanese stays readable when a judge opens the file.
The reports gain the same. JSON readers see identical data either way, and every file is written
as UTF-8.

### D3. `e2e_seed` gets the helper too

Its sessions file is read by Playwright's global setup. A trailing newline and a
`CommandError` on failure change nothing for that reader; a traceback becomes one line.

## Risks / Trade-offs

- [A test compares exact bytes of a report] → the tests read files with `json.loads`; any that
  compare text are updated in the same change.
- [Error wording changes] → no test or script parses it; README and docs do not quote it.
