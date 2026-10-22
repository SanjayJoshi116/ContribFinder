## Context

The rows are independent. Most touch one function each. The current state, per row, as
re-verified on 2026-10-22:

- **GitHub client.**
  - `_record_rate_limit` (`services/github/client.py`) writes `github:ratelimit:{scope}` on
    every response. Nothing reads it, and `data_deletion` purges `github:ratelimit:{pk}` (A-16).
  - `_get` returns the cached body on a 304 but leaves the entry's TTL alone (A-17).
  - `cache.get` / `cache.set` are unguarded. With `RedisCache` an outage raises after
    `REDIS_SOCKET_TIMEOUT`, and the job fails through its retry policy. Batch 5 deferred this
    here (its design, Non-Goals).
  - `core/throttling.py` already has a per-process backoff for the throttle cache
    (`THROTTLE_CACHE_BACKOFF_SECONDS`).
- **Health.** `check_redis` builds `redis.Redis.from_url(...)` (a new pool) on every call
  (A-20).
- **Profile read.** `developers/api.py` annotates `Count("skills", distinct=True)` and
  `Count("interests", distinct=True)` on one queryset. That is a skills × interests join
  (B-17).
- **Freshness.** `due_profiles` already computes every input as an annotation. The last step
  is a Python list comprehension over all profiles with candidates or recommendations (D-21).
- **Discovery.** `_update_metadata` sends the whole merged `metadata` dict through
  `save_progress` after every analysis. That dict holds the query plan, rejections, the
  analysis plan and the growing `analyzed` list (C-20).
- **Snapshots.** The saved list, the recommendation list and detail, and
  `matching/features.py` each `Prefetch("repository__snapshots", order_by(-captured_at, -pk),
  to_attr="ordered_snapshots")`. Each then reads only `[0]`. Up to `REPO_SNAPSHOT_HISTORY` rows
  per repository are loaded (E-10).
- **Completion.** `lifecycle.complete` calls `eligibility`. That reads `repo.topics.all()` and
  `repo.dependencies.exists()` right after `_store` wrote them (X-11).
- **Scripts.**
  - `stop.mjs` lists processes, then reads records (Z-4).
  - `redis.mjs` records the keep-alive even when `spawn` returned no pid (Z-5).
  - On Linux the process name comes from `ps comm=` (Z-8).
  - Every match gets its own `killTree` `spawnSync` (Z-9).

## Goals / Non-Goals

**Goals:**
- Same observable results with fewer queries and writes. Existing tests stay green unchanged,
  except where a test reached into a removed helper or attribute.
- One home for each duplicated helper or fixture.

**Non-Goals:**
- A-18. Moving a profile sync's repository endpoints to `PUBLIC_SCOPE` would leave the user's
  repository data in the shared cache after "delete my data" (spec `data-controls`, "the
  user's cached GitHub responses"). It stays per user and is recorded `wontfix` with that
  reason.
- X-8 (stays `wontfix`). Y-6, Y-7 and Z-1 (open, not in this batch). Any ranking or
  explanation change (batch 8).
- A local fallback store for ETag entries while Redis is down. A miss costs one counted
  request, and a per-process copy of response bodies is memory for little gain.

## Decisions

**D1. Response cache errors are a miss (A-16, spec `github-data-sync`).** `_get` reads and
writes the ETag cache through two small guarded helpers.
- Any exception from the cache logs a warning and marks the cache down for this process for
  `GITHUB_CACHE_BACKOFF_SECONDS` (new, default 30, positive-integer check in the GitHub check
  group).
- While the cache is down, `_get` sends an unconditional request and does not store the result.
- The monotonic-deadline helper moves out of `core/throttling.py` into a shared
  `core/backoff.py` (`Backoff(setting_name, what)` with `down()` and `mark_down(exc)`). Both
  the throttles and the client use it, each with its own instance and setting.
- `_record_rate_limit` is deleted. The `github:ratelimit:{pk}` purge in `data_deletion` is
  deleted too: no key is written any more, and old keys expire within their one-hour TTL.
- *Alternative:* one shared backoff for throttles and the client. Rejected: the web process
  would stop using the cache for GitHub data because a throttle call failed, and the two
  settings have different audiences.

**D2. 304 renews the entry (A-17).** On 304 with a cached entry, call
`cache.touch(key, settings.GITHUB_ETAG_TTL)`, inside the D1 guard. A failed touch is a cache
error like any other.

**D3. One Redis client per process (A-20).** `check_redis` uses a module-level client built
lazily on first use, under a `functools.cache`-wrapped factory keyed by URL. redis-py clients
are thread-safe and reconnect by themselves. Timeouts stay 2 s.

**D4. Counts as subqueries (B-17).** Replace the two `Count(distinct=True)` with
`Coalesce(Subquery(<related>.filter(profile=OuterRef("pk")).values("profile")
.annotate(c=Count("pk")).values("c")), 0)` for skills and for interests. Each is one indexed
count with no join between them. The serializer fields are unchanged.

**D5. Freshness filter in SQL (D-21).** The final comprehension becomes a `.filter()`:
`Q(last_generation__isnull=True) | Q(outdated_config=True) |
Q(analyzed_at__gt=F("last_generation")) | Q(pool_changed__gt=F("last_generation")) |
Q(data_changed__gt=F("last_generation")) | Q(has_candidates=False)`.
- SQL null comparisons are false. That matches the Python `t is not None and t > …` guards.
- `analyzed_at` is non-null.
- The function still returns a list of profiles with `user` selected.
- The existing freshness tests are the equivalence check. One test with many non-due profiles
  asserts the query count stays constant.

**D6. Metadata merged on the server (C-20).** New `job_guard.merge_metadata(job, **values)`:
- It runs `held(job).update(metadata=<metadata || values::jsonb>, updated_at=now)`, with a
  `Func` using PostgreSQL's `||`.
- It raises `JobCancelled` like `save_progress`.
- It applies the same merge to the in-memory `job.metadata`.
- `DiscoveryService._update_metadata` calls it, so each analysis sends only `analyzed` and
  `analysis_outcomes`.
- `analyzed` still grows by one id per analysis, so its size is linear in the run (at most
  `DISCOVERY_MAX_ANALYSES_PER_RUN` ids). The quadratic part was resending everything else.
- *Alternative:* save progress every N analyses. Rejected: a resumed step would redo up to N
  analyses, and their outcomes would be counted twice.
- *Alternative:* `jsonb_set` per key. That gives the same result with more SQL.

**D7. Latest-snapshot prefetch (E-10).** New `repositories.queries.latest_snapshot(prefix="")`
returns `Prefetch(f"{prefix}snapshots", queryset=RepositorySnapshot.objects
.order_by("-captured_at", "-pk")[:1], to_attr="latest_snapshots")`. Django 5 supports sliced
prefetch querysets (one window query). The three call sites use it, and the serializers and
features read `latest_snapshots[0]` when present. The new module lives in the `repositories`
app, next to the model. The name `ordered_snapshots` goes away, so a missed caller fails
loudly.

**D8. Eligibility takes known inputs (X-11).**
- `filters.eligibility(repo, *, now, cfg, topics=None, has_dependencies=None)` and
  `stored_not_code` use given values instead of reading them.
- `lifecycle.complete(repo, *, now, topics=None, has_dependencies=None)` passes them through.
- `RepositoryAnalysisService._store` returns the topics and dependency presence it wrote: None
  for a part not fetched in this run, which is then read as today.
- `recheck_eligibility` and bulk callers are unchanged (they annotate).

**D9. Small cleanups.**
- B-20: the docstring says languages "by skill confidence".
- C-21: `ineligible_reason` gets `read_only=True`, then `npm run api:sync`.
- C-23: `queue_refresh_backlog` asks one `has_app_credentials()` function in `services/github/oauth.py`, which
  `GitHubClient.for_app` also uses.
- D-19: `join_names(items)` moves to `services/text.py`, used by the summary and issue
  reasons. `matching/issues.py` imports `GOOD_FIRST_ISSUE` and `HELP_WANTED` from
  `services/issues/labels.py`. `repositories/analysis.py` keeps its raw GitHub label strings
  (they are label names, not categories).
- D-20: `score_candidate` computes `value` with `weighted_score` instead of repeating the sum.

**D10. Test helpers (X-12, Y-9, Y-10, Z-10).**
- X-12: `make_developer`, `developer`, `single_band` (autouse) and the public-scope GitHub
  client (`public_client`, registered as `client`) move to `tests/shared_fixtures.py`, which
  the modules that use them import. *As built:* not `conftest.py`, because a global `client`
  fixture would replace pytest-django's test client in `test_data_deletion`, `test_github_auth`
  and `test_sync_api`. Importing fixtures makes every test parameter an F811 for ruff, which the
  tests already silenced line by line; `tests/**` now ignores F811. Modules whose `client`
  differs (other cache scopes) keep their own.
- Z-10: `ids` (check ids from a result) goes to `tests/checks_helpers.py`. The
  `EXPERIENCE_THRESHOLDS` tests move into `test_profiling_config.py`.
- Y-9: the database builders `e2e_seed` uses (`add_candidate`, `fresh_repo`, `make_issue`)
  (and `make_candidate_repo`, which they build on) move to `e2e/builders.py`, and
  `tests/repo_fixtures.py` re-exports them. `e2e/builders.py` imports nothing from `tests`.
  *As built:* `tests/test_e2e_seed.py` (frontend-correctness) already runs `_seed_pool` and
  `_synced_user` against the test database, so a builder change that breaks `npm run e2e`
  already fails pytest; no new test was needed.
- Y-10: `callsTo(fetchMock, method, url)` moves to `src/test/render.tsx`. `app.test.tsx`
  counts with `callsTo(...).length`.

**D11. Stop script (Z-4, Z-5, Z-8, Z-9).**
- Z-4: `stop.mjs` calls `readRecords()` before `processes()`. A runner that starts between the
  two then has a live process, so its record is never judged stale.
- Z-5: `redis.mjs` records the keep-alive only when `keepAlive.pid` is a number. The comment
  says: detached for its own console; on Windows still a child, so `taskkill /T` of the runner
  reaches it; the record covers `npm run stop` when the runner is already gone.
- Z-8: on non-Windows, `ps -eo pid=,args=`. `name` is the basename of the first argument,
  lowercased (the real executable). `comm` is dropped.
- Z-9: `killTree(pids)` accepts one pid or an array. On Windows it runs one `taskkill /T /F`
  with a `/pid` per pid (taskkill continues past pids already gone). On POSIX it loops
  `process.kill(-pid)`. Existing single-pid callers are unchanged.

## Risks / Trade-offs

- [`||` on JSON is PostgreSQL-specific] → PostgreSQL is the system of record and the test
  database. The Func lives in one helper.
- [Sliced prefetch issues a window query] → It is still one query per prefetch, now returning
  one row per repository. Covered by the existing serializer tests, plus a query-count test on
  the saved list.
- [Cache backoff hides a persistent Redis outage in workers] → Each transition to down logs a
  warning. Broker loss still stops the worker, so an outage stays visible.
- [Fixture moves change test collection] → Run the full suite before and after. Fixture names
  and behavior are unchanged.

## Migration Plan

- No database migration.
- One new optional setting (`GITHUB_CACHE_BACKOFF_SECONDS`), documented in `.env.example`.
- Old `github:ratelimit:*` keys expire within an hour.
- Rollback is a code revert.
