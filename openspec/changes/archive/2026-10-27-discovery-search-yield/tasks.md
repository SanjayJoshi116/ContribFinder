## 1. Recording (D1, D2)

- [x] 1.1 `services/discovery/queries.py`: `PlannedQuery.band` (`band_label` with more than one
  band, `""` otherwise), in `as_json`; a stored plan without `band` loads. Tests: banded and
  single-band plans, loading an old plan dict.
- [x] 1.2 `services/discovery/service.py` `_step_search`: per query, `query_yield[key]` with
  source, band, results, rejections (pre-filter and storing `not_code`) and recorded; a 422 query
  as `refused`. Written in the same `merge_metadata` call as `queries_done` / `queries_skipped`.
- [x] 1.3 Tests: the spec scenarios "Yield per query", "Refused query in the yield", "One star
  band"; a resumed run keeps the earlier queries' yield and adds the rest; totals unchanged; no
  query text in `query_yield`.

## 2. Report (D3, D4)

- [x] 2.1 `services/discovery/yield_report.py`: `load(since)`, `build(runs)`, `YieldReport.as_dict()`.
- [x] 2.2 `repositories/management/commands/discovery_report.py` (`--since`, `--json`).
- [x] 2.3 Tests: spec scenarios "Rejections per strategy" (0.50 vs 0.85), "Yield per band",
  "Runs from before the yield was recorded", "Aggregates only" (JSON has no identifiers or query
  text; every key walked); active (RUNNING/PENDING) jobs are left out; `--since` window; bad
  options refused; no stored row changes.

## 3. Verification and housekeeping

- [x] 3.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; `git diff --exit-code
  apps/backend/evaluation/baselines.json`; root `check:version`. No frontend or e2e change.
- [x] 3.2 Manual: run discovery once on the dev database, then `npm run manage --
  discovery_report` and `--json ../../reports/discovery.json`.
- [x] 3.3 Docs: README (discovery report section), CLAUDE.md §6 command line and §7 shipped
  entry (K-1 carry-over unchanged), `ideas.md` §12 (both items to "Shipped" as measurement; what a
  budget change would need stays open), `features.txt`.
- [x] 3.4 Release housekeeping (CLAUDE.md §8): patch 0.12.25; `CHANGELOG.md`, `features.txt`,
  README status line; lockfiles.
