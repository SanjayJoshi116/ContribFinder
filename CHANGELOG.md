# Changelog

All notable changes to ContribFinder are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows
[Semantic Versioning](https://semver.org/). Before the MVP, each completed roadmap phase bumps
the minor version (`0.x.0`).

## [Unreleased]

## [0.2.0] - 2026-09-28

Phase 2: GitHub data ingestion (OpenSpec change `phase-2-github-ingestion`; FR-GH-001..007, FR-DATA-001).

### Added

- Background GitHub sync fetches the user's profile, profile README (stored raw), public owned
  repositories (up to 100, most recently pushed), their languages (bytes) and topics into
  PostgreSQL. Later phases read this stored data instead of calling GitHub.
- GitHub client (`services/github/client.py`):
  - follows pagination (with a page cap) and uses ETag conditional requests (a 304 reuses the
    cached body);
  - handles primary and secondary rate limits (`Retry-After` / reset time) and maps errors to
    typed exceptions;
  - only follows pagination links on the API host.
- Tracked, resumable jobs (`SyncJob`): PENDING → RUNNING → COMPLETED / FAILED / RETRYING /
  CANCELLED, with per-step progress, attempt count and a safe error code.
  - A database constraint allows only one active job per user.
  - Retries never repeat completed steps.
  - Rate-limit waits and exponential backoff are capped.
  - A token rejected by GitHub (401) fails the job immediately, without retrying.
- API:
  - `POST /api/v1/profile/sync` returns 202, or 409 `github_not_connected`, or 429 `sync_cooldown`
    with `Retry-After`;
  - `GET /api/v1/sync/status`;
  - `GET /api/v1/profile/github`;
  - `GET /api/v1/profile/repositories` (paginated, `page_size` up to 100).
- The first sign-in starts a sync automatically. Disconnecting GitHub cancels any sync in progress.
- Frontend:
  - an onboarding screen with live per-step progress and messages for each failure;
  - a dashboard with profile, language breakdown, repositories, last-synced time and Refresh
    (with a cooldown message).
- Local development uses real background processing: `npm start` now also starts the WSL Redis
  service (Windows) and a Celery worker (`--pool=solo`). `REDIS_URL` defaults to
  `redis://localhost:6379/1`.
- `npm run check:version` also checks the three lockfiles.
- Tests: 142 backend and 22 frontend. Verified end to end with real GitHub: the first sync
  completed on the first attempt (~9s), and the Refresh cooldown works.

### Changed

- Custom API exceptions keep their own error code; for example `not_synced` is no longer reported
  as `not_found`.
- Logout moved into a shared signed-in layout. The disconnect text now says that synced data is
  kept until data deletion ships.

### Fixed

- Test isolation: respx routes registered outside an active mock leaked into later tests. Tests now
  use the `respx_mock` fixture, and an autouse guard resets the global router.
- `npm start` / `npm run setup` failed with "uv not found" when uv was installed via
  `pip install --user` (not on PATH) and `python` was the Microsoft Store stub. The runner now
  also checks standard install folders (`%APPDATA%\Python\Python3xx\Scripts`, `~/.local/bin`,
  `~/.cargo/bin`), accepts a `UV_BIN` override, and lists everything it tried.

### Known limitations

- Synced GitHub data is kept after disconnect until data deletion ships (FR-DATA-003, Phase 8a).
- No automatic periodic refresh yet; syncs run on first sign-in or on Refresh.
- The Docker Compose stack is still unverified (no Docker on the development machine).

## [0.1.0] - 2026-09-28

Phase 1: Foundation (OpenSpec change `phase-1-foundation`; FR-AUTH-001..003).

### Added

- Monorepo: `apps/backend` (Django 5.2, DRF, Celery) and `apps/frontend` (React 19, TypeScript,
  Vite, Tailwind v4, shadcn/ui, TanStack Query, React Router).
- GitHub sign-in through an OAuth App with no scopes (public data only). The flow uses a single-use
  `state`, and the user is matched by GitHub ID, so signing in again after disconnecting reuses the
  same user.
- GitHub access tokens are encrypted at rest (MultiFernet with key rotation). They are never
  returned to the client, and a log filter masks them as a backstop.
- Session auth with HTTP-only cookies and CSRF protection. New endpoints:
  `GET /api/v1/auth/github`, `GET /api/v1/auth/github/callback`, `GET /api/v1/auth/csrf/`,
  `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/github/disconnect`.
- Disconnect revokes the grant on GitHub and deletes the stored credential, even when the
  revocation call fails.
- Audit log for sign-in, failed sign-in, logout and disconnect. Metadata keys are allowlisted and
  client IPs are stored only as salted hashes.
- API platform:
  - every endpoint lives under `/api/v1/` and returns errors as `{"error": {code, message, details}}`;
  - unauthenticated requests get 401;
  - rate limiting returns 429 with `Retry-After`;
  - CORS allowlist and security headers;
  - `GET /api/v1/health/` checks the database and Redis;
  - OpenAPI schema at `GET /api/v1/schema/`.
- Frontend: landing page with messages for each sign-in error, a route guard, and a signed-in page
  with logout and a confirmed disconnect. API types are generated from the OpenAPI schema
  (`npm run api:sync`).
- Local development without Docker: `npm run setup` and `npm start` (Django on :8000, Vite on
  :5173) against a local PostgreSQL. Redis is optional; without it the cache is in-process, Celery
  tasks run inline, and health reports Redis as `not_configured`.
- Docker Compose stack: Postgres with pgvector, Redis, backend, Celery worker and beat, frontend.
- CI (GitHub Actions):
  - backend: ruff, strict mypy, migration check, pytest on Postgres;
  - frontend: eslint, prettier, tsc, vitest, build;
  - checks that the committed API schema matches the backend, and that the version is consistent
    across `VERSION` and the manifests.
- Tests: 60 backend and 12 frontend.

### Security

- Production settings refuse to start without `REDIS_URL` and force HTTPS, HSTS and Secure
  cookies.
- System check `core.E001` blocks startup when `TOKEN_ENCRYPTION_KEYS` is missing or invalid.

### Known limitations

- The Docker Compose stack and the Celery worker in Docker have not been verified yet (no Docker on
  the development machine). This is carried over to Phase 2.
- The API contract version (`/api/v1`, OpenAPI `1.0.0`) is versioned separately from the app
  version.

[Unreleased]: https://github.com/SanjayJoshi116/ContribFinder/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/SanjayJoshi116/ContribFinder/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/SanjayJoshi116/ContribFinder/releases/tag/v0.1.0
