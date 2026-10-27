## Context

See proposal.md for why.
- `plan_queries` (`services/discovery/queries.py`) builds `PlannedQuery(source, q, key, core)`
  per strategy, core and star band. The band is only visible in `q` (`stars:...`) and in the key
  suffix `@<index>`; `band_label(band)` gives `20..999` / `1000+`. The plan is stored in
  `job.metadata["plan"]` and reloaded with `PlannedQuery(**q)` when the search step resumes.
- `_step_search` (`services/discovery/service.py`) records run totals in the metadata:
  `queries_done`, `queries_skipped` (422), `rejections` (per reason, pre-filter plus `not_code`
  found while storing; the interactions step adds to the same counter) and `results_found`.
  Writes go through `merge_metadata` (JSON merge under the claim) after each query, so a resumed
  run never repeats a query.
- Discovery jobs are `SyncJob(job_type="repository_discovery")`; deleting a user's data deletes
  them, so a report only sees jobs of users who still have their data.
- `feedback_report` (0.12.20) is the pattern for an aggregate-only report: `load` (one query) +
  pure `build` + `as_dict`, a management command that prints and optionally writes JSON to the
  gitignored `reports/`.

## Goals / Non-Goals

**Goals:**
- Per-query yield recorded by every new run, at no extra GitHub request.
- One command that turns finished runs into per-strategy and per-band figures.

**Non-Goals:**
- Changing queries, shares, bands or the budget (a later change, justified by this report).
- Measuring the interactions step (it makes no search request) or analysis outcomes.
- An API or interface for the report.

## Decisions

**D1. `PlannedQuery.band` holds the band label.**
- `band: str = ""`: `band_label(band)` when more than one band is configured, `""` otherwise
  (the plan without bands is unchanged). `as_json` writes it; a plan stored by an older run has
  no `band` key and loads with `""` through the default.
- *Alternative:* parse the band from `q` or the key suffix in the report. Rejected: it couples the
  report to the query text format, and the report must not read query text at all.

**D2. `query_yield` in the job metadata, keyed by query key.**
- `{key: {"source", "band", "results", "rejections": {reason: n}, "recorded"}}` for a query that
  ran; `{"source", "band", "refused": true}` for a 422. Written in the same `merge_metadata` call
  as `queries_done` (or `queries_skipped`), so the totals and the per-query entry never disagree
  after a resume. The key is the stable id already used for resuming (`language:python@0`); it
  names a skill or topic, never the full query, and the report never outputs it.
- `results` counts what GitHub returned (as `results_found` does); `recorded` counts the results
  recorded as candidates for this query (after pre-filtering and the `not_code` check while
  storing).
- *Alternative:* a table of query results. Rejected: job metadata already holds per-run
  progress, the data is small (at most `DISCOVERY_MAX_QUERIES` entries per run) and a table
  needs a migration and its own deletion path.

**D3. Report service: `services/discovery/yield_report.py`.**
- `load(since)`: one `values_list("metadata")` query over discovery jobs with status COMPLETED,
  FAILED or CANCELLED, `started_at >= since` when given; it reads only `query_yield` from each.
- `build(runs) -> YieldReport` (pure): rows per strategy, per band and per (strategy, band), plus
  a total row. Each row: requests, refused, results, rejections (per reason, most frequent
  first), recorded, `results_per_request` (results / requests that ran), `recorded_share`
  (recorded / results; None without results). Runs without `query_yield` count in
  `runs_without_yield`. Strategy is the discovery source (`language_search`, …); an empty band
  reads `all`.
- `as_dict()` for JSON; numbers rounded like the other reports (`metrics.PLACES`).
- *Alternative:* extend `feedback_report`. Rejected: different source data and readers.

**D4. Command `discovery_report` in the `repositories` app.**
- `repositories/management/commands/discovery_report.py` (the app that owns discovery): `--since
  DAYS` (at least 1), `--json OUT` (folders created; `OSError` → `CommandError`). Prints the total,
  then the strategy table, the band table and the strategy × band table, each with rejections
  listed as `no_license 9, archived 1`.

## Risks / Trade-offs

- [Few runs locally, so figures are noisy] → The report shows request and run counts next to
  every share; decisions wait for enough runs.
- [Overlapping queries find the same repository, so `recorded` counts discoveries, not distinct
  repositories] → Documented as candidates recorded per query; distinct pool size is already
  `pool_bands`.
- [Runs started before the upgrade but finished after it record yield only for the queries run
  after it] → Those runs enter the report with partial yield; acceptable for a measurement.

## Migration Plan

- No migration. Deploy; new runs record `query_yield`, older runs are counted as without yield.
- Rollback: revert the release; the extra metadata keys are ignored.
