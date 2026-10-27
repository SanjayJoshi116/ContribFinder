## 1. Cleanup (D1, D2, D3)

- [x] 1.1 `services/discovery/service.py`: `_record_pool(extra)` (pool size and bands plus the
  given counters); the pool step uses it.
- [x] 1.2 `_step_analysis`: keep the ids analyzed with outcome `analyzed` in the metadata
  (`analysis_succeeded`); after the loop, inside `job_write`, `_remove_not_code` on them and
  `_record_pool({"analysis_not_code": removed})`.
- [x] 1.3 Tests:
  - spec "List found by this run's analysis" (new `awesome-*` without dependencies: gone after
    the run, `analysis_not_code` 1, `pool_size` / `pool_bands` without it, shared row kept and
    ineligible `not_code`);
  - "Code project analyzed" (`awesome-lint` with dependencies stays);
  - a failed analysis removes nothing; a cancelled run (job no longer RUNNING) removes nothing;
  - a resumed analysis step still cleans up with the recorded ids;
  - existing pool-step metadata unchanged.

## 2. Verification and housekeeping

- [x] 2.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; `git diff --exit-code
  apps/backend/evaluation/baselines.json`; root `check:version`. No frontend or e2e change.
- [x] 2.2 Docs: CLAUDE.md §7 shipped entry (K-1 carry-over unchanged), `ideas.md` §11 item to
  "Shipped", `Bug_Backlog.md` X-9 fixed (index, totals), `features.txt`.
- [x] 2.3 Release housekeeping (CLAUDE.md §8): patch 0.12.26; `CHANGELOG.md`, `features.txt`,
  README status line; lockfiles.
