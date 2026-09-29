## Why

Users can sign in (v0.1.0), but ContribFinder knows nothing about them yet. Every later phase (skill extraction, discovery, ranking) reads the user's GitHub data from our own database, never live from GitHub (SRS-2 §44, Decision 4). This phase fetches that data into PostgreSQL through background jobs that respect GitHub's rate limits. It also sets up the job pattern (tracked jobs, retries, progress) that later phases reuse.

## What Changes

- Add a GitHub API client used only by the sync layer. It handles authentication with the user's stored token, pagination, timeouts, conditional requests (ETags), rate limits (primary and secondary), retry with backoff, and response caching.
- Fetch and store the user's GitHub profile (username, name, bio, company, location, blog, followers, following, public repo count, account creation date).
- Fetch and store the user's public owned repositories with metadata (SRS-2 §10), their language breakdowns and topics.
- Fetch the profile README from `{username}/{username}` and store it raw, separate from any derived data. A missing README is a normal outcome, not a failure.
- Add a generic tracked background job (`SyncJob`) with states PENDING, RUNNING, COMPLETED, FAILED, RETRYING and CANCELLED, per-step progress, attempt count and a safe error code.
- API:
  - `POST /api/v1/profile/sync` starts a sync and returns immediately, with a cooldown and at most one active sync per user;
  - `GET /api/v1/sync/status` returns progress and the last successful sync time;
  - `GET /api/v1/profile/github` and `GET /api/v1/profile/repositories` expose the synced data.
- A user's first sign-in starts a sync automatically. Disconnecting GitHub cancels any sync in progress.
- Frontend:
  - an onboarding screen that polls sync progress with per-step ticks;
  - the signed-in page shows the synced profile, repositories, languages, the last-synced time and a Refresh button.
- Local development gets a real broker: Redis runs inside WSL (Ubuntu). `npm start` also starts a Celery worker, which closes the Phase 1 worker carry-over locally.

## Capabilities

### New Capabilities
- `github-data-sync`: Fetching the user's GitHub profile, profile README, public repositories, languages and topics into ContribFinder, including pagination, rate limits, transient failures and credential handling (FR-GH-001 to FR-GH-007).
- `sync-jobs`: Starting, tracking and reporting background synchronization (single active job, cooldown, per-step progress, failure states, initial sync after sign-in, cancellation on disconnect) and exposing the synced data (FR-DATA-001).

### Modified Capabilities
<!-- None. The sync started at first sign-in and the cancellation on disconnect are specified in sync-jobs; github-authentication behaviour is unchanged. -->

## Impact

- **Backend**: new apps `jobs` (SyncJob) and `repositories` (Repository, RepositoryLanguage, RepositoryTopic, UserRepository); `github` gains GitHubProfile and sync tasks; `services/github/client.py`, `services/github/sync.py`; new endpoints under `/api/v1/profile/` and `/api/v1/sync/`; migrations.
- **Frontend**: onboarding route, sync-status hook with polling, profile/repository views; regenerated API types.
- **Local dev**: `redis-server` installed in WSL Ubuntu; `.env` gets `REDIS_URL=redis://localhost:6379/0`; `npm start` adds a Celery worker (`--pool=solo` on Windows) and makes sure WSL Redis is running.
- **GitHub API usage**: about 3 + N requests per sync (N = repositories, for language data), within the 5,000/hour authenticated limit. The per-sync repository cap is configurable.
- **Privacy**: GitHub-derived data is now stored. Deleting it on user request is FR-DATA-003 (Phase 8a). Until then, disconnect removes the credential and cancels syncs but keeps the synced data.
- **Carry-over**: verifying the Docker Compose stack stays deferred (no Docker). The local real-worker check is covered here.
