## Context

Phase 1 (v0.1.0) provides sign-in, an encrypted per-user GitHub token (`services/crypto.py`), the `/api/v1` platform (error envelope, CSRF, throttling), the Celery app (`config/celery.py`, eager when `REDIS_URL` is empty) and the OAuth-only `services/github/oauth.py`. Nothing reads GitHub data yet. Development happens on Windows without Docker; PostgreSQL 18 is local, and Ubuntu is installed under WSL2. Requirements are in `specs/github-data-sync` and `specs/sync-jobs`; motivation is in `proposal.md`.

## Goals / Non-Goals

**Goals:**
- A GitHub client that stays within rate limits and that later phases (repository discovery, issues) reuse unchanged.
- A generic, resumable, observable job model that later jobs reuse (skill extraction, embeddings, recommendations).
- Real asynchronous behaviour locally (real broker and worker), matching production.

**Non-Goals:**
- Periodic background refresh (Celery beat schedules). Syncs are user-triggered or run at first sign-in for now.
- Contribution history (commits, PRs, reviews), dependency manifests, private repositories and organization repositories. These are Phase 3 and later.
- Deleting synced data (FR-DATA-003, Phase 8a) and deriving skills or interests (Phase 3).
- Docker Compose verification (still deferred; no Docker on the dev machine).

## Decisions

### D1. App boundaries and data model
- `jobs.SyncJob`: `user, job_type ("github_profile_sync"), status, steps (JSON {step: state}), attempts, error_code, error_detail (safe text), metadata (JSON: caps and truncation flags), created_at, started_at, completed_at`. A partial unique constraint on `user` where `status IN (PENDING, RUNNING, RETRYING)` enforces one active job per user in the database, not only in code. It lives in its own app because later jobs are not GitHub-specific.
- `github.GitHubProfile` (1:1 User): the profile fields from the spec, `has_profile_readme`, `profile_readme` (raw text, never modified), `synced_at`. Raw GitHub data stays here. Phase 3 derived data goes into `developers`.
- `repositories.Repository` (unique `github_id`, unique `full_name`) with the SRS-2 §10 metadata, plus `RepositoryLanguage(repository, language, bytes)` and `RepositoryTopic(repository, topic)`, both unique per pair.
- `repositories.UserRepository(user, repository, relation="owner")`: a link table. The same `Repository` row serves later as a discovery candidate (Phase 4), so repository data isn't duplicated per user.
- **Alternative**: JSON blobs on the profile (languages and topics as JSON). Rejected because CLAUDE.md requires relational core entities, and Phase 3/5 query across languages and topics.

### D2. One orchestrating task with resumable steps
- `github.tasks.sync_github_profile(job_id)` takes only the job ID, never a token. It loads the job, moves it PENDING/RETRYING → RUNNING with a conditional `UPDATE ... WHERE status IN (...)`, so a duplicate delivery exits without work. It then runs `services/github/sync.py: GitHubSyncService.run(job)`.
- Steps run in a fixed order: `profile → readme → repositories → languages → topics`. Topics come from the repositories payload, so they cost no extra requests. Each step saves its state to `job.steps` when it finishes. On retry, steps already `done`/`not_found` are skipped. The languages step saves per-repository progress in `job.metadata` so a retry continues where it stopped.
- The service raises typed errors. The task converts them into Celery retries or a terminal state, so the retry policy is in one place and the service can be tested without Celery.
- **Alternative**: a Celery chain or chord of per-step tasks. Rejected: harder to cancel, spreads retry state across tasks, and fans out per-repository tasks that fight over the same rate-limit budget.

### D3. GitHub client (`services/github/client.py`)
- `GitHubClient(token)` is created by `GitHubClient.for_user(user)`, which decrypts the token at that one point. It uses `httpx.Client` with the configured timeout and headers `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, `Authorization: Bearer`.
- Methods return normalized frozen dataclasses (`GitHubUser`, `GitHubRepo`), never raw JSON: `get_authenticated_user()`, `list_owned_repositories(login)` (`/users/{login}/repos?type=owner&sort=pushed&per_page=100`), `get_languages(full_name)`, `get_profile_readme(login)` (`/repos/{login}/{login}/readme` with `Accept: application/vnd.github.raw`; 404 → `None`).
- `_paginate()` follows `Link: rel="next"` up to `GITHUB_MAX_PAGES` (default 10), and reports truncation to the caller.
- **Conditional requests**: per user and URL, the Django cache (Redis) stores `{etag, body}` for 24h. The request sends `If-None-Match`, and a 304 returns the cached body. If the cache has been evicted, the request is simply unconditional; that costs a request but can't give wrong results. Keys never contain the token (`github:etag:{user_id}:{sha256(url)}`).
- **Error mapping**:
  - 401 → `GitHubAuthError`.
  - 403/429 with `Retry-After`, or with `X-RateLimit-Remaining: 0` → `GitHubRateLimited(retry_after)`.
  - Other 403, and 404 → `GitHubNotFound` / `GitHubForbidden`.
  - 5xx and `httpx.TransportError` → `GitHubTransientError`.
  - Messages include status and path only, never headers or bodies.
- Rate-limit headers from each response are stored in the cache (`github:ratelimit:{user_id}`) so they can be observed.

### D4. Retry policy (task layer)
- `GitHubRateLimited`: countdown = `retry_after` plus a small jitter. If it exceeds `GITHUB_MAX_RETRY_DELAY` (default 900s), the job fails with `github_rate_limited`.
- `GitHubTransientError`: exponential backoff `min(30 · 2^attempt, 600)` with jitter, up to `SYNC_MAX_ATTEMPTS` (default 5), then `github_unavailable`.
- `GitHubAuthError`, or no connected account: `github_auth_invalid` / `github_not_connected`, with no retry.
- The job is RETRYING while waiting, and `attempts` counts executions. Retries go through `self.retry(countdown=...)`. There is never a sleep or loop inside the worker.

### D5. Starting jobs, cooldown, cancellation
- `services/jobs.py: start_profile_sync(user) -> (job, created)` runs in a transaction. It returns the active job if one exists, and rejects the start with `SyncCooldown(retry_after)` inside `SYNC_COOLDOWN_SECONDS` (default 300) of the last COMPLETED job. Otherwise it creates a PENDING job and queues the task with `transaction.on_commit`. The partial unique constraint catches a race between two concurrent requests, which returns the existing job.
- First sign-in: the OAuth callback calls `start_profile_sync` when the user has no COMPLETED job and none active. This is queued, so the redirect isn't delayed.
- Disconnect: the Phase 1 view marks active jobs CANCELLED before deleting the account. The service checks the job status before each step and each repository's language request, and stops if the job is CANCELLED.

### D6. API
- `POST /api/v1/profile/sync` → 202 `SyncJob`. Errors: 409 `github_not_connected`, 429 `sync_cooldown` with `Retry-After`.
- `GET /api/v1/sync/status` → `{job: SyncJob | null, last_synced_at}`.
- `GET /api/v1/profile/github` → `GitHubProfile` (404 `not_synced`).
- `GET /api/v1/profile/repositories` → paginated, with languages and topics loaded via prefetch, ordered by `pushed_at` descending.
- `SyncJob` serializer fields: `id, status, steps, attempts, error_code, created_at, started_at, completed_at`. `metadata` and `error_detail` stay internal.

### D7. Frontend
- `useSyncStatus()` (TanStack Query) polls every 2s while the job is PENDING/RUNNING/RETRYING and stops otherwise. `useStartSync()` sends the POST and treats 429 as "try later", showing the time remaining.
- Routes: `/onboarding` shows the step checklist with states and error messages mapped from `error_code`. `/app` redirects to `/onboarding` when `last_synced_at` is null. `/app` shows the profile summary, a language breakdown aggregated client-side from the repository list, the repository list, the last-synced time and Refresh.

### D8. Local broker: the existing WSL Redis service, kept awake by `npm start`
- Found during implementation: Ubuntu under WSL2 already has `redis-server` 8.0.5 as an enabled, running systemd service on `127.0.0.1:6379`, and db 0 already holds other keys. Running a second foreground `redis-server` on the same port would collide, so ContribFinder reuses the service and uses **db 1** (`REDIS_URL=redis://localhost:6379/1`) to stay clear of other data.
- `scripts/redis.mjs` (run by `npm start` on Windows when `REDIS_URL` points at localhost): `wsl -d Ubuntu -u root -- systemctl start redis-server` (no sudo password with `-u root`; no-op if already running), then keeps a `wsl -d Ubuntu -- sleep infinity` session attached for the lifetime of `npm start`. WSL shuts an idle distro down once no session is attached, which would stop Redis.
- WSL2 localhost forwarding (NAT mode, default) takes a few seconds after the distro starts. `scripts/wait-port.mjs` waits for `127.0.0.1:6379` before the Celery worker starts. Node resolves `localhost` to `::1` first, so the wait targets IPv4 explicitly.
- The Celery worker runs with `--pool=solo` (prefork is unsupported on Windows).
- If `REDIS_URL` is empty, the Phase 1 eager fallback still works, but `npm start` warns that syncs will block the request.
- **Alternatives**: a separate foreground `redis-server` on another port (duplicates an already-working service); Memurai (not chosen); WSL mirrored networking (changes global WSL config for all distros).

### D9. Configuration (settings/env, all optional with defaults)
`GITHUB_SYNC_MAX_REPOS=100`, `GITHUB_MAX_PAGES=10`, `GITHUB_MAX_RETRY_DELAY=900`, `SYNC_MAX_ATTEMPTS=5`, `SYNC_COOLDOWN_SECONDS=300`, `GITHUB_ETAG_TTL=86400`.

## Risks / Trade-offs

- [WSL2 localhost forwarding slow to start, disabled or firewalled] → `wait-port` retries for up to 30s, then prints a clear error. Fallback: set `REDIS_URL` to the WSL IP (`wsl hostname -I`).
- [Shared Redis instance with other local data] → ContribFinder uses db 1 only; nothing in the app calls `FLUSHALL`/`FLUSHDB`.
- [Language requests scale with repository count, about 100 requests] → capped by `GITHUB_SYNC_MAX_REPOS`. ETags make repeat syncs mostly 304s, which don't count against the primary limit.
- [Worker crash mid-step leaves a job RUNNING forever] → `acks_late` redelivers the task, and the conditional RUNNING transition plus saved steps resume it. A job RUNNING with no update for more than 30 minutes is treated as stale and not active, so the user can start a new one.
- [Synced data kept after disconnect] → documented privacy gap until FR-DATA-003 (Phase 8a); covered in the proposal's Impact section.
- [Celery eager mode in tests hides retry countdowns] → the retry policy is a pure function tested directly. The service is tested with respx fixtures, and the task wrapper is tested with `retry` mocked.
- [Partial unique index is PostgreSQL-specific] → SQLite is no longer used anywhere (dev, CI and tests all use Postgres).

## Migration Plan

Additive migrations only (new tables); no changes to existing data. Existing users have no sync job, so they see onboarding on their next visit, and a sync starts on the next sign-in or via Refresh. Rollback: revert the change and the migrations. No other data depends on the new tables yet.
