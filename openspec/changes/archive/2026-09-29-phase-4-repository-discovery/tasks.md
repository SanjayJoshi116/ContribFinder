## 1. Data model (design D1)

- [x] 1.1 Add to `Repository`: `lifecycle` (TextChoices, default `discovered`, indexed), `lifecycle_changed_at`, `lifecycle_error`, `previous_lifecycle`, `stale_parts` JSON, `is_eligible` (nullable), `ineligible_reason`, community and label nullable bools, `readme_synced_at`, `community_synced_at`, `dependencies_synced_at`, `activity_synced_at`
- [x] 1.2 Add `RepositoryReadme` (1:1, content, size, truncated, fetched_at) and `RepositorySnapshot` (signals, `prs_sample_capped`, nullable unknowns, `activity_label`, `thresholds_version`, ordered `-captured_at`)
- [x] 1.3 Add `RepositoryCandidate` (FK `DeveloperProfile`, unique developer+repository, index developer+`-last_seen_at`) and `CandidateDiscovery` (source choices, query, search_rank, first/last seen, unique candidate+source+query)
- [x] 1.4 Add `SyncJob.JobType.REPOSITORY_DISCOVERY`. Generate migrations (`--settings config.settings.test`). Register read-only admin views (candidates with discoveries inline, snapshots, lifecycle filter)
- [x] 1.5 Tests: unique constraints; candidate cascade on profile delete; repository kept when a candidate is deleted; README and snapshots cascade with the repository; existing repositories migrate to `discovered`

## 2. Configuration (design D9)

- [x] 2.1 Add the `DISCOVERY_*`, `REPO_*` and `ACTIVITY_THRESHOLDS` settings with env overrides and `CELERY_BEAT_SCHEDULE` (mark stale hourly, backlog every 15 minutes). Document them in `.env.example`
- [x] 2.2 Extend `core/checks.py`: positive budgets and caps, results per query ≤ 100, known share and stale-part keys, moderate thresholds not stricter than recent. Tests for valid and invalid configs

## 3. Shared storage helpers and GitHub client (design D2, D5)

- [x] 3.1 Move `_upsert_repository`, `_replace_languages`, `_replace_topics` and `_read_manifests` into `services/github/storage.py` as public functions. Update `sync.py` imports. The existing sync tests pass unchanged
- [x] 3.2 Refactor `GitHubClient` auth to an `auth_header` value: `for_user` (Bearer), `for_app()` (Basic client credentials, scope `app`, `GitHubAuthError` when unset), plus a `cache_scope` override. `__repr__` and logs stay secret-free
- [x] 3.3 Add `search_repositories`, `get_community_profile`, `list_label_names`, `get_readme`, `count_commits_since` (day-truncated `since`, Link-last count, 409 → 0), `count_contributors` (Link-last, 403/204 → `None`), `recent_pull_requests` (one page, 90-day counts, capped flag) and `get_latest_release_date` (404 → `None`), with normalized dataclasses
- [x] 3.4 respx fixture tests: search results and 422; community profile; labels with normalization; README present and 404; commit count from the Link header, without Link, and 409; contributors unknown on 403; PR sample counts and cap; release 404; the app client sends Basic auth and never logs the secret; the `public` cache scope shares ETags between two user clients

## 4. Pure discovery stages (spec: repository-discovery; design D3, D4)

- [x] 4.1 Implement `services/discovery/queries.py`: `DiscoveryInput`, `PlannedQuery`, the four strategies, qualifying-skill rule (confidence and non-README evidence), qualifiers (day-granular push date, stars, `-user:`), budget shares with carry-over, dedup, stable keys
- [x] 4.2 Tests: Python/Django/dev-tooling example; a README-only skill gives no query; budget 10 out of 25 possible allocated by shares; carry-over when a strategy is empty; deterministic output; sparse profile → empty plan; quoting of multi-word linguist names
- [x] 4.3 Implement `services/discovery/filters.py` `prefilter` and `eligibility` with reason codes (`archived`, `fork`, `inactive`, `no_license`, `few_stars`, `own_repository`, `repository_unavailable`). `NOASSERTION` counts as licensed; stars not checked for `previously_interacted`. Tests per reason

## 5. Activity signals (spec: repository-activity; design D6)

- [x] 5.1 Implement `services/matching/activity.py`: `ActivityData`, `ActivitySignals`, `compute_activity` with the configured thresholds, unknown handling (push date only, never `recently_active`) and `thresholds_version`
- [x] 5.2 Tests: recently active; moderately active; low activity at 200 days; counts unknown → moderately active; merged-PR path to recently active; threshold change relabels; deterministic

## 6. Repository analysis and lifecycle (spec: repository-analysis; design D5, D8)

- [x] 6.1 Implement `services/repositories/lifecycle.py`: `claim` (conditional update, fetching vs refreshing, reclaim of stale claims, store `previous_lifecycle`), `release`, `fail(code)`, `complete` (analyzed → indexed → recommendable/indexed via `eligibility`)
- [x] 6.2 Implement `services/repositories/analysis.py` `RepositoryAnalysisService.analyze(repo, parts)`: fetch the requested parts (metadata + languages + topics, README with truncation, community + labels, dependencies via `read_manifests`, activity), write them in one transaction, set per-part timestamps, insert the snapshot and trim the history. Error mapping per design D5
- [x] 6.3 Implement `services/repositories/staleness.py` `stale_parts` (pure) and the tasks `repositories.mark_stale_repositories`, `repositories.process_repository_backlog`, `repositories.sync_repository` and `repositories.sync_repository_readme` (app client, IDs only, retry through `decide_retry` with release, no-op with a warning without client credentials)
- [x] 6.4 Tests: first analysis ends RECOMMENDABLE with every part stored; an ineligible repository ends INDEXED with a reason; missing README, CONTRIBUTING and labels are not failures; 404 → FAILED `not_found` and candidates ineligible `repository_unavailable`; rate limit → state restored, not FAILED; a concurrent claim is refused and a stale claim reclaimed; README truncation; snapshot history trimmed to 10; `stale_parts` per data type; mark-stale only touches pooled RECOMMENDABLE/INDEXED repositories; the backlog selects stale, discovered-after-grace and failed-due repositories, only pooled ones, capped at the batch; a refresh fetches only stale parts (request assertions); refresh uses Basic auth and decrypts no user token

## 7. Discovery job (spec: repository-discovery, sync-jobs; design D7)

- [x] 7.1 Extract the retry/finish loop from `github.tasks.sync_github_profile` into `services/jobs.run_tracked_job`. Parameterize `active_jobs`/`_expire_stale` by job type. The existing sync and job tests pass unchanged
- [x] 7.2 Implement `services/discovery/service.py` `DiscoveryService(job)` with the steps queries, search, interactions, analysis and pool: plan in metadata, per-query resume, 422 → skipped query, prefilter counts, candidate and discovery upserts, previously-interacted candidates, capped and ordered analysis with per-repository progress and cancellation checks, retention and pool-cap eviction
- [x] 7.3 Add task `discovery.generate_candidates(job_id)` using `run_tracked_job`, and `start_discovery(user)` (needs a profile and a GitHub account; returns the active job). Call it on commit after a COMPLETED sync and a COMPLETED profile analysis
- [x] 7.4 Extend disconnect handling so a cancelled discovery releases the repository it was analyzing (the claim is restored on `JobCancelled`)
- [x] 7.5 Tests:
  - a full run stores candidates with provenance and metadata counts;
  - a repository found by two queries gives one candidate with two discovery records;
  - rediscovery updates `last_seen_at` without duplicates;
  - an own repository is never a candidate;
  - a contributed repository is a `previously_interacted` candidate, exempt from stars;
  - a retry after a rate limit resumes the remaining queries only (request counts);
  - a sparse profile completes with `search` skipped;
  - a fresh shared repository is not re-fetched for a second developer;
  - the analysis cap is honored, and the rest stay DISCOVERED;
  - expired candidates are removed;
  - the pool cap evicts least recently seen, previously-interacted last;
  - 401 → FAILED `github_auth_invalid`;
  - a completed sync/analysis starts discovery, a failed one does not, an active discovery is not duplicated;
  - no profile → no job;
  - disconnect cancels discovery and leaves no repository FETCHING;
  - no token in job fields, task args or logs
- [x] 7.6 Dead-worker recovery: `SyncJob.heartbeat()` called from `_check_cancelled` in sync and discovery; `SYNC_STALE_AFTER_SECONDS` default 10 min; beat task `jobs.recover_stale_jobs` (every 5 min) requeues abandoned RUNNING jobs, and fails those at `SYNC_MAX_ATTEMPTS` with `worker_lost`; `lifecycle.claim` stamps the wall clock; the backlog also takes `fetching | refreshing` claims older than the stale threshold; `REDIS_SOCKET_TIMEOUT` for the cache and broker connect. Tests: `test_job_recovery.py`, backlog and claim tests in `test_repository_analysis.py`
- [x] 7.7 Parallel analysis: `DISCOVERY_ANALYSIS_CONCURRENCY` threads (default 4, test settings 1), progress recorded by the job thread, first error re-raised after the others finish their current repository; local worker `--pool=threads --concurrency=$CELERY_CONCURRENCY` (4). Tests: transactional `test_analysis_runs_in_parallel` (barrier proves concurrency) and `test_parallel_failure_keeps_finished_work_and_raises`

## 8. Discovery API (spec: repository-discovery; design D10)

- [x] 8.1 Implement `GET /api/v1/discovery/status` (latest discovery job, last completed time, pool counts incl. `awaiting_analysis` and `by_source`) and `GET /api/v1/discovery/candidates` (paginated, repository summary, lifecycle, eligibility and reason, latest activity label, discoveries, first and last seen; filters `source`, `eligible`, `activity`; ordered by `-last_seen_at`; no score field)
- [x] 8.2 Tests: response shapes; never-discovered status; counts; each filter; user isolation; 401 when signed out; no GitHub request (respx asserts none); query count does not grow with page size
- [x] 8.3 Regenerate the OpenAPI schema and TypeScript types (`npm run api:sync`)

## 9. Frontend (spec: repository-discovery; design D11)

- [x] 9.1 Add `useDiscoveryStatus()` (polls while the job is active, invalidated when a sync completes) and `DiscoveryCard` on the profile page (no-job, active, completed with eligible count and relative time, failed with a mapped message). No scores, percentages or lists
- [x] 9.2 Tests (Vitest + RTL): each card state; transition from active to completed without reload; failed-message mapping; no "%" rendered

## 10. Local tooling, verification, docs and release

- [x] 10.1 Add `scripts/beat.mjs` (Celery beat through `uv`, schedule file in a temp dir) and start it from `scripts/start.mjs` when `REDIS_URL` is set. Update the README's local-run section
- [x] 10.2 Manual check: `GET /rate_limit` with the app client credentials returns an authenticated public-data limit (the design D8 assumption). Record the result in design Risks
- [x] 10.3 Manual end-to-end with `npm start` (WSL Redis, worker, beat) on a real account: after Refresh, the discovery card goes from finding to N candidates; the candidates API shows sources and activity labels; the backlog task analyzes the remaining DISCOVERED repositories; mark-stale followed by the backlog refreshes a repository
- [~] 10.4 Carry-over: verify `docker compose up` (incl. `beat`) from a fresh `.env` on a machine with Docker. If still impossible, mark it `[~]` and carry it to Phase 5 — no Docker on the dev machine (2026-09-29); carried over to Phase 5
- [x] 10.5 Release housekeeping per CLAUDE.md §8 at archive time (v0.4.0): versions and lockfiles, CHANGELOG, features.txt, README status, CLAUDE.md (Phase 4 shipped, `services/repositories/` in the layout, the RepositoryCandidate/CandidateDiscovery deviation, carry-overs to Phase 5)
