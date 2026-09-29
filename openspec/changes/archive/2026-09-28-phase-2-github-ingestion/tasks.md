## 1. Local broker (WSL Redis) and worker

- [x] 1.1 Install `redis-server` in WSL Ubuntu (found already installed: 8.0.5, systemd service enabled) and confirm Windows reaches `127.0.0.1:6379` (PONG after forwarding warm-up)
- [x] 1.2 Add `scripts/redis.mjs` (start the WSL `redis-server` service and keep the distro awake with an attached session; exit with a clear message when WSL or redis-server is missing) and `scripts/wait-port.mjs` (wait until a TCP port accepts connections)
- [x] 1.3 Extend root `npm start`: when `REDIS_URL` is set, run redis (Windows/WSL only), backend, Celery worker (`--pool=solo` on Windows, waits for Redis) and frontend via `concurrently`; when `REDIS_URL` is empty, keep the current behaviour and print a warning that syncs will block
- [x] 1.4 Set `REDIS_URL=redis://localhost:6379/1` in local `.env` (and update `.env.example` comments); verify the worker runs `core.ping` asynchronously against WSL Redis (closes the Phase 1 local worker carry-over)

## 2. Data model

- [x] 2.1 Create `jobs` app with `SyncJob` (status/step enums, `steps` JSON, attempts, error_code, error_detail, metadata, timestamps) and a partial unique constraint for one active job per user
- [x] 2.2 Add `github.GitHubProfile` (1:1 user; profile fields, `has_profile_readme`, raw `profile_readme`, `synced_at`)
- [x] 2.3 Create `repositories` app with `Repository`, `RepositoryLanguage`, `RepositoryTopic`, `UserRepository` (unique constraints and indexes on `pushed_at`, `full_name`)
- [x] 2.4 Generate migrations; add settings `GITHUB_SYNC_MAX_REPOS`, `GITHUB_MAX_PAGES`, `GITHUB_MAX_RETRY_DELAY`, `SYNC_MAX_ATTEMPTS`, `SYNC_COOLDOWN_SECONDS`, `GITHUB_ETAG_TTL`; register admin views (read-only, no token fields)
- [x] 2.5 Tests: one-active-job constraint rejects a second active job for the same user but allows a new job after completion; unique language/topic pairs

## 3. GitHub client (spec: github-data-sync)

- [x] 3.1 Implement `services/github/client.py`: `GitHubClient.for_user(user)` (single decrypt point), headers, timeout, normalized dataclasses `GitHubUser`, `GitHubRepo`
- [x] 3.2 Implement error mapping: `GitHubAuthError` (401), `GitHubRateLimited(retry_after)` (403/429 with `Retry-After` or remaining=0 and reset), `GitHubNotFound`, `GitHubForbidden`, `GitHubTransientError` (5xx and transport errors); messages contain status and path only
- [x] 3.3 Implement `_paginate()` following `Link: rel="next"` up to `GITHUB_MAX_PAGES`, reporting truncation
- [x] 3.4 Implement ETag conditional requests via the Django cache (`github:etag:{user_id}:{sha256(url)}`); 304 returns the cached body; store rate-limit headers under `github:ratelimit:{user_id}`
- [x] 3.5 Implement `get_authenticated_user`, `list_owned_repositories` (type=owner, sort=pushed), `get_languages`, `get_profile_readme` (raw; 404 → None)
- [x] 3.6 Tests (respx): multi-page pagination; page cap truncation; 304 reuse; 401; 403 + Retry-After; 403 + remaining=0 + reset; 429; 502 and timeout → transient; README 404 → None; captured logs and exception messages contain no token

## 4. Sync service and task

- [x] 4.1 Implement `services/github/sync.py: GitHubSyncService.run(job)` with ordered steps profile → readme → repositories → languages → topics; skip steps already done; persist step state and per-repo language progress; check for CANCELLED before each step and each language request
- [x] 4.2 Implement persistence: upsert `GitHubProfile`; upsert `Repository` by `github_id`; relink `UserRepository` (unlink repos no longer returned); replace languages/topics per repo; apply `GITHUB_SYNC_MAX_REPOS` (most recently pushed) and record caps and truncation in job metadata
- [x] 4.3 Implement the pure retry policy `decide_retry(error, attempts) -> Retry(countdown) | Fail(code)` (rate limit with max delay, exponential backoff with jitter, auth/not-connected → fail)
- [x] 4.4 Implement Celery task `github.tasks.sync_github_profile(job_id)`: conditional PENDING/RETRYING → RUNNING transition (duplicate delivery exits), run the service, map errors through `decide_retry` to `self.retry(countdown=…)` / RETRYING or FAILED with error_code, COMPLETED with timestamps; `acks_late`
- [x] 4.5 Tests: full sync stores profile, README, repos (fork flagged), languages, topics; no-README user completes with `not_found`; unlink of removed repo; repo cap applied; retry resumes without re-fetching completed steps (assert request counts); `decide_retry` table tests; cancelled job stops before next request; 401 → FAILED `github_auth_invalid` without retry; job fields and task args contain no token

## 5. Job API and triggers (spec: sync-jobs)

- [x] 5.1 Implement `services/jobs.py: start_profile_sync(user)`: return the active job, cooldown check (`SyncCooldown(retry_after)`), create a PENDING job and enqueue with `transaction.on_commit`; treat RUNNING jobs not updated for 30 minutes as stale
- [x] 5.2 Implement `POST /api/v1/profile/sync` (202 / 409 `github_not_connected` / 429 `sync_cooldown` + Retry-After) and `GET /api/v1/sync/status` (`{job, last_synced_at}`, own jobs only)
- [x] 5.3 Implement `GET /api/v1/profile/github` (404 `not_synced`) and `GET /api/v1/profile/repositories` (paginated, prefetch languages/topics, pushed_at desc); no GitHub calls
- [x] 5.4 Start the initial sync from the OAuth callback for users with no completed and no active job; cancel active jobs in the disconnect view before deleting the account
- [x] 5.5 Tests: 202 new job; second start returns the same job; cooldown 429 with Retry-After; 409 without account; status never-synced / running / other user isolation; first sign-in enqueues a job and redirect is immediate; returning user does not; disconnect cancels an active job; data endpoints make no GitHub requests (respx asserts none); 404 `not_synced`
- [x] 5.6 Regenerate OpenAPI schema and TypeScript types (`npm run api:sync`)

## 6. Frontend

- [x] 6.1 Add `useSyncStatus()` (polling every 2s while active), `useStartSync()`, `useGitHubProfile()`, `useRepositories()` hooks using generated types
- [x] 6.2 Build `/onboarding`: step checklist (pending / running / done / not found / failed), readable messages per `error_code` (re-sign-in for `github_auth_invalid`, retry for others), move to `/app` when completed
- [x] 6.3 Redirect `/app` to `/onboarding` when `last_synced_at` is null; show profile summary, language breakdown (aggregated bytes), repository list with topics, last-synced time and Refresh button (cooldown message on 429)
- [x] 6.4 Tests (Vitest + RTL): onboarding shows step progress and navigates on completion; failure messages per error code; `/app` redirect when never synced; Refresh starts a sync and handles cooldown; languages aggregated correctly

## 7. Verification, docs and release

- [x] 7.1 Manual end-to-end with `npm start` (WSL Redis + worker): first sign-in shows onboarding progress, data appears, Refresh respects cooldown, disconnect during a sync cancels it
- [x] 7.2 Run all checks: ruff, mypy, pytest (Postgres), eslint, prettier, tsc, vitest, build, `openspec validate`, `check:version`
- [x] 7.3 Update `CLAUDE.md` (Phase 2 shipped, commands for Redis/worker, layout: `jobs`, `repositories`), `README.md` (WSL Redis setup), `features.txt`, `CHANGELOG.md`; bump version to 0.2.0 across `VERSION` and manifests
