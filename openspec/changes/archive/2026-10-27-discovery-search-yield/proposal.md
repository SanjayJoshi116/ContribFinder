## Why

Discovery spends a fixed request budget (default 20 searches per run, split across star bands),
but a run records only totals: results found and rejections per reason. The first real run
rejected 30 results as `no_license` against 3 `not_code`, and nobody can tell which strategy
(language, skill, interest, topic) or which star band wasted those slots. `ideas.md` §12 lists both
gaps ("`no_license` is the biggest rejection", "Uneven band yield"), next in the "can ship now"
list. Measuring per strategy and band is the step before any query or budget change: such a
change would alter what users are recommended, so it must be justified by data first. No ranking
change: this only records and reports.

## What Changes

- Each planned search query records its star band (or none, when only one band is configured).
- Every discovery run records, per query it ran: strategy, star band, results returned,
  rejections per reason and candidates recorded, plus whether GitHub refused the query. The
  existing totals stay as they are.
- New management command `discovery_report [--since DAYS] [--json OUT]`: over finished discovery
  runs in the window, per strategy and per star band (and per strategy × band): requests, results,
  rejections per reason, candidates recorded, results per request and the share of results
  recorded. Runs from before this change are counted on their own line. Aggregates only: no user,
  query text, repository or job identifiers. Read-only.
- No API, interface or ranking change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repository-discovery`:
  - "Candidate search": each query's star band, and its yield recorded on the run;
  - new requirement "Discovery yield report".

## Impact

- Backend:
  - `services/discovery/queries.py`: `PlannedQuery.band` (label, `""` with one band; plans
    stored by older runs load with `""`);
  - `services/discovery/service.py`: per-query yield in the job metadata (`query_yield`);
  - `services/discovery/yield_report.py` (new): `load(since)` (one query over discovery jobs),
    `build(...)` (pure), JSON form;
  - `repositories/management/commands/discovery_report.py` (new);
  - tests.
- No migration (job metadata is JSON), no frontend change, no new setting.
- Release: patch 0.12.25. Docs: README (discovery report), CLAUDE.md §6 command line and §7,
  `ideas.md` §12 (both items shipped as measurement), CHANGELOG, features.
