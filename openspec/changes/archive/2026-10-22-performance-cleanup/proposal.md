## Why

Batch 11 of `Bug_Backlog.md` (rows A-16, A-17, A-18, A-20, B-17, B-20, C-20, C-21, C-23, D-19,
D-20, D-21, E-10, DOC-1, DOC-2, X-11, X-12, Y-9, Y-10, Z-4, Z-5, Z-8, Z-9, Z-10, re-verified
against the code on 2026-10-22; C-22 was already fixed in batch 4). These rows are wasted work
and duplicated code that shipped batches left for later:
- the GitHub client writes a rate-limit cache entry nobody reads;
- the client lets valid ETag entries expire, which costs counted requests;
- a worker job fails when the response cache errors, although the cache only saves requests
  (deferred here by batch 5);
- profile reads and the recommendation freshness sweep do work in Python or in large joins
  that SQL can do in one row;
- discovery rewrites the whole job metadata after every analysis;
- the saved, recommendation and feature queries load every activity snapshot to read the
  newest;
- helpers and test fixtures are copied between modules, and one installed command imports
  test code;
- `npm run stop` has a record race and a Linux name mismatch, and spends one `taskkill` per
  process;
- two lines of `features.txt` are out of date.

None of this changes ranking, so it does not wait for K-1. It is the last open batch apart
from batch 8 (ranking-visible, waits for K-1).

## What Changes

- **GitHub client (A-16, A-17, A-18).**
  - Drop the unread `github:ratelimit:{scope}` entry, and its purge in data deletion.
  - A 304 renews the ETag entry's lifetime.
  - A response-cache error makes the request unconditional instead of failing it. The process
    then skips the cache for a short backoff.
  - A-18 (public endpoints of a profile sync cached per user) is **wontfix**. Those entries
    describe the user's own repositories. A shared scope would let them outlive "delete my
    data" (spec `data-controls`), and the hit rate gained is small.
- **Health check (A-20).** One Redis client per process, not one per request.
- **Profile read (B-17).** Skill and interest counts come from two subqueries, not one
  cross-product join.
- **Freshness sweep (D-21).** `due_profiles` filters in SQL. Only due profiles leave the
  database.
- **Discovery progress (C-20).** Analysis progress merges only the changed metadata keys into
  the stored JSON on the server side.
- **Latest snapshot (E-10).** One shared prefetch loads only each repository's newest snapshot.
  The saved list, recommendations and feature loading use it.
- **Eligibility after analysis (X-11).** `complete` passes the topics and dependency presence
  the analysis just stored, so they are not read back.
- **Code cleanup (B-20, C-21, C-23, D-19, D-20).** A correct summary docstring.
  `ineligible_reason` is read-only in the OpenAPI schema (regenerated client types). One
  app-credentials check. One name-joining helper. Label constants imported from `labels.py`.
  `score_candidate` uses `weighted_score`.
- **Test code (X-12, Y-9, Y-10, Z-10).**
  - Shared backend fixtures move to `conftest.py`, with one `ids` helper.
  - Seeding helpers move to a module that both `e2e_seed` and the tests import.
  - One frontend request-count helper.
  - The `EXPERIENCE_THRESHOLDS` tests move to the profiling config tests.
- **Stop script (Z-4, Z-5, Z-8, Z-9).**
  - Records are read before the process list.
  - The keep-alive is recorded only with a real pid, and its comment is corrected.
  - On Linux the executable name comes from the command line, not `comm`.
  - All matched pids go to one `taskkill`.
- **Docs (DOC-1, DOC-2).** `features.txt` drops the stale Ctrl+C carry-over and points the
  judging carry-over at `real-a-v2`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-data-sync`: "Conditional requests" adds two rules. A 304 keeps the stored response
  usable for another full cache lifetime. An unavailable response cache makes a request
  unconditional and never fails it.

## Impact

- Backend:
  - `services/github/client.py`, `services/data_deletion.py`, `core/health.py`,
    `developers/api.py`.
  - `services/ranking/freshness.py`, `services/ranking/score.py`.
  - `services/discovery/service.py`, `services/job_guard.py`.
  - `services/repositories/lifecycle.py`, `services/repositories/analysis.py`,
    `services/discovery/filters.py`.
  - The latest-snapshot prefetch and its three users: `feedback/api.py`,
    `recommendations/api.py`, `services/matching/features.py`.
  - `repositories/serializers.py`, `repositories/tasks.py`, `services/matching/issues.py`,
    `services/profiling/summary.py`.
  - New setting `GITHUB_CACHE_BACKOFF_SECONDS` (default 30, with a startup check).
- Test code: `tests/conftest.py`, the test modules that copied fixtures, a seeding module
  shared with `e2e/management/commands/e2e_seed.py`, `src/test/render.tsx`.
- Scripts: `scripts/stop.mjs`, `scripts/stack.mjs`, `scripts/redis.mjs`, `scripts/child.mjs`.
- OpenAPI: `ineligible_reason` becomes read-only (non-breaking). `npm run api:sync`
  regenerates `schema.d.ts`.
- No ranking, API behavior or UI change. Patch release 0.12.10.
