## 1. GitHub response cache (D1, D2, A-16, A-17)

- [x] 1.1 `core/backoff.py`: `Backoff(setting_name, what)` with `down()` and
  `mark_down(exc)` (monotonic deadline, one warning per transition). `core/throttling.py`
  uses it, and its tests stay green.
- [x] 1.2 Setting `GITHUB_CACHE_BACKOFF_SECONDS` (default 30) in `base.py` and `.env.example`,
  with a positive-integer check in the GitHub check group (`core.E020`). Add a test for the
  check.
- [x] 1.3 `services/github/client.py`: guarded `_cache_get` / `_cache_set` / `_cache_touch`.
  While the cache is down, `_get` sends no `If-None-Match` and stores nothing. On a 304,
  `touch` the entry with `GITHUB_ETAG_TTL`.
- [x] 1.4 Delete `_record_rate_limit`, and the `github:ratelimit:{pk}` purge in
  `services/data_deletion.py`, with its test assertion.
- [x] 1.5 Tests (respx): a cache that raises on get/set → the request is unconditional, the
  result is returned and no exception escapes; a second request within the backoff does not
  call the cache; a 304 renews the TTL (an entry past its original expiry is still sent
  conditionally); no `github:ratelimit:*` key is written. One sync test with a failing cache
  completes.

## 2. Queries (D3, D4, D5, D7, A-20, B-17, D-21, E-10)

- [x] 2.1 `core/health.py`: a cached Redis client factory keyed by URL. Test: two calls create
  one client.
- [x] 2.2 `developers/api.py`: skill and interest counts as `Coalesce(Subquery(...), 0)`. Test
  the counts for a profile with several skills and interests, and the query count.
- [x] 2.3 `services/ranking/freshness.py`: replace the comprehension with the D5 `Q` filter.
  Existing freshness tests pass. Add a test: N non-due profiles plus one due → only the due
  profile is returned, in a constant number of queries.
- [x] 2.4 `repositories/queries.py`: `latest_snapshot(prefix="")` (sliced `Prefetch`,
  `to_attr="latest_snapshots"`). Use it in `feedback/api.py`, `recommendations/api.py` and
  `services/matching/features.py`, and read `latest_snapshots` in both serializers and
  features. No `ordered_snapshots` left (`grep`).
- [x] 2.5 Test: a repository with several snapshots → saved list, recommendation detail and
  features use the newest. The saved list's query count does not grow with the snapshot
  count.

## 3. Discovery and analysis writes (D6, D8, C-20, X-11)

- [x] 3.1 `services/job_guard.py`: `merge_metadata(job, **values)` (`metadata || values`
  through a `Func`, `JobCancelled` unless held, in-memory merge too). Unit tests: merge keeps
  other keys and keys written concurrently; it raises when cancelled or reclaimed.
- [x] 3.2 `DiscoveryService._update_metadata` uses `merge_metadata`. Discovery tests pass. Add
  a test that a concurrently added metadata key survives an analysis progress write.
- [x] 3.3 `filters.eligibility` / `stored_not_code` take optional `topics` and
  `has_dependencies`. `lifecycle.complete` passes them through.
  `RepositoryAnalysisService._store` returns what it wrote, and the analysis passes it on.
- [x] 3.4 Test: an analysis that fetched metadata and dependencies completes without reading
  topics or dependencies back (query count). One that fetched neither still reads them, with
  the same eligibility result as before.

## 4. Code cleanup (D9, B-20, C-21, C-23, D-19, D-20)

- [x] 4.1 `services/profiling/summary.py`: docstring says languages "by skill confidence".
- [x] 4.2 `repositories/serializers.py`: `ineligible_reason` `read_only=True`. Then `npm run
  api:sync` and commit `schema.d.ts` and the schema.
- [x] 4.3 `services/github/oauth.py`: `has_app_credentials()`. `GitHubClient.for_app` and
  `repositories/tasks.py` use it, and `_has_app_credentials` is removed.
- [x] 4.4 `services/text.py`: `join_names`, used by `profiling/summary.py` and
  `matching/issues.py`. `matching/issues.py` imports `GOOD_FIRST_ISSUE`, `HELP_WANTED` from
  `services/issues/labels.py`.
- [x] 4.5 `services/ranking/score.py`: `score_candidate` uses `weighted_score`. The
  `baselines.json` test is unchanged (no ranking change).

## 5. Test helpers (D10, X-12, Y-9, Y-10, Z-10)

- [x] 5.1 Move `developer`, `single_band` and the plain GitHub `client` fixture to a shared
  module (as built: `tests/shared_fixtures.py`, imported; see design D10). Remove the copies.
  Modules with a different `client` keep theirs.
- [x] 5.2 `tests/checks_helpers.py`: one `ids`, used by the five modules. Move the
  `EXPERIENCE_THRESHOLDS` tests into `test_profiling_config.py`. Drop the overlap with
  `test_default_config_is_valid` (keep one).
- [x] 5.3 `e2e/builders.py`: `add_candidate`, `fresh_repo` and `make_issue` (moved, no
  `tests` import). `tests/repo_fixtures.py` re-exports them, and `e2e_seed` imports from
  `e2e.builders`.
- [x] 5.4 pytest test that imports `e2e_seed` and runs `_seed_pool` and one `_synced_user` in
  the test database (already there: `tests/test_e2e_seed.py`, kept as is).
- [x] 5.5 Frontend: `callsTo` in `src/test/render.tsx`. Use it in `app.test.tsx` (replacing
  `count`) and `feedback.test.tsx`.
- [x] 5.6 Full backend suite passes with the same test count as before the moves (apart from
  the tests added here).

## 6. Stop script (D11, Z-4, Z-5, Z-8, Z-9)

- [x] 6.1 `stop.mjs`: read records before the process list.
- [x] 6.2 `redis.mjs`: record the keep-alive only for a numeric pid, and correct the comment.
- [x] 6.3 `stop.mjs` (POSIX): `ps -eo pid=,args=`. The name is the basename of the first
  argument. Test the parser with a `MainThread`-style case in `scripts/*.test.mjs` (move the
  parsing into a pure exported function).
- [x] 6.4 `child.mjs` `killTree(pidOrPids)`: one `taskkill /T /F /pid … /pid …` on Windows,
  and a loop on POSIX. `stop.mjs` passes all matched pids at once.
- [x] 6.5 Manual: `npm start`, then `npm run stop` from a second prompt stops the stack; no
  record left in `.run/`.

## 7. Verification and housekeeping

- [x] 7.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`. Frontend lint,
  format:check, typecheck, test, and `npm run e2e`. `npm run test:scripts`. `npm run
  check:version`.
- [x] 7.2 `features.txt`: drop or close the stale Ctrl+C `[~]` line (DOC-1). Point the judging
  carry-over at `real-a-v2` (40 candidates), with K-1 still open (DOC-2).
- [x] 7.3 `Bug_Backlog.md`: mark A-16, A-17, A-20, B-17, B-20, C-20, C-21, C-23, D-19, D-20,
  D-21, E-10, DOC-1, DOC-2, X-11, X-12, Y-9, Y-10, Z-4, Z-5, Z-8, Z-9, Z-10 `fixed
  (performance-cleanup)`. Mark A-18 `wontfix` with the privacy reason. Update the shipped line
  (batch 11) and name what is next (batch 8 after K-1; Y-6, Y-7, Z-1 open).
- [x] 7.4 CLAUDE.md:
  - §4 layout: `core/backoff.py`, `repositories/queries.py`, `services/text.py`,
    `e2e/builders.py`.
  - §5: GitHub cache errors are a miss with backoff; drop "rate-limit state in Redis" from the
    FR-GH-007 sketch.
  - §7: add the shipped entry.
- [x] 7.5 Release housekeeping (CLAUDE.md §8), patch release 0.12.10:
  - `VERSION`, the package files and lockfiles;
  - `CHANGELOG.md`, `features.txt`, README status line.
