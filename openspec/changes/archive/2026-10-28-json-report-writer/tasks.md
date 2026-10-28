## 1. Helper

- [x] 1.1 `apps/backend/core/reports.py`: `json_text(data)` (indent 2, `ensure_ascii=False`,
  trailing newline) and `write_json(out, data, *, what)` (parent folders created, UTF-8,
  `OSError` → `CommandError("<what> not written to <out>: <reason>")`).
- [x] 1.2 Tests: nested folder created; non-ASCII kept and the file reads back with
  `json.loads`; trailing newline; a write into a path whose parent is a file raises
  `CommandError` naming `what` and the path.

## 2. Commands

- [x] 2.1 `evaluate_ranking`, `feedback_report`, `discovery_report` (`--json`): `write_json(...,
  what="Report")`.
- [x] 2.2 `export_benchmark_developer` (`--out` via `write_json(what="Export")`, else
  `json_text` to stdout), `import_judgments` (`what="Judgments"`), `build_benchmark`
  (`what="Benchmark"`).
- [x] 2.3 `e2e_seed` (`what="Sessions"`).
- [x] 2.4 No command imports `json` only to write files any more; grep confirms no
  `mkdir(parents=True` left in `*/management/commands/` except `benchmark_sheet`.

## 3. Verification and housekeeping

- [x] 3.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest` (the command tests and
  the e2e seed tests pass unchanged or with updated message checks); `git diff --exit-code
  apps/backend/evaluation/baselines.json`.
- [x] 3.2 Docs: `Bug_Backlog.md` T-14 fixed; `ideas.md` §15 item moved to Shipped; CLAUDE.md
  §4 (`core/reports.py`) and §7 entry; `features.txt`; `CHANGELOG.md`.
- [x] 3.3 Release housekeeping (CLAUDE.md §8): patch version, lockfiles, `check:version`;
  archive the change.
