## Context

This is a greenfield repo: only the SRS documents, `CLAUDE.md` and OpenSpec exist. `CLAUDE.md` already fixes the stack, the monorepo layout (`apps/backend`, `apps/frontend`) and the invariants (modular monolith, Celery for GitHub work, tokens never exposed). This change sets the patterns every later phase copies, so the choices below favour conventions that scale over the quickest demo. Requirements are in `specs/github-authentication` and `specs/api-platform`.

## Goals / Non-Goals

**Goals:**
- `docker compose up` gives a working stack with no manual steps beyond filling `.env`.
- A thin, auditable OAuth flow we control end to end, so token handling can be verified.
- Establish the Django project shape, test setup, error format, and the OpenAPI → TypeScript pipeline that later phases reuse.

**Non-Goals:**
- Fetching any GitHub data beyond the identity returned at sign-in (Phase 2).
- Deleting GitHub-derived data or accounts (FR-DATA-003, Phase 8a). Disconnect here removes only the credential and the link.
- Production deployment, Sentry/Prometheus, and E2E tests with Playwright (Playwright can't drive real GitHub OAuth. It comes with the onboarding flow).
- Any UI beyond landing, the signed-in shell and error display.

## Decisions

### D1. GitHub OAuth App with a hand-rolled flow (not django-allauth, not a GitHub App)
- **Choice**: Register an OAuth App. Implement authorize → callback → token exchange with `httpx` in `services/github/oauth.py`. Views stay thin.
- **Why**: The only credential we need is a user token to read public data. allauth stores tokens in plaintext `SocialToken` rows and brings a lot of extra machinery. Encrypting them means patching its models. The flow is about 100 lines, fully testable with mocked HTTP, and keeps token handling in one file.
- **Alternatives**: *django-allauth* (plaintext tokens, heavy); *GitHub App* (installation model and per-repo permissions add complexity we don't need to read public data; can revisit if rate limits force it).
- **Scopes**: empty scope list (`GITHUB_OAUTH_SCOPES=""`). An unscoped token can already read public user, repo and README data. Make it configurable. `CLAUDE.md`'s `read:user` note is corrected to "no scopes" in this change.
- **State**: 32-byte `secrets.token_urlsafe` stored in the session. It's single-use and deleted when read. Callback rejects missing or mismatched state before calling GitHub.

### D2. Token encryption: explicit service, Fernet with key rotation
- **Choice**: `GitHubAccount.access_token_encrypted` (binary/text ciphertext) plus `services/crypto.py` exposing `encrypt_token` / `decrypt_token`, built on `cryptography.fernet.MultiFernet` with keys from `TOKEN_ENCRYPTION_KEYS` (comma-separated, newest first).
- **Why**: Explicit encrypt/decrypt calls make every plaintext touch point greppable. MultiFernet supports key rotation without downtime.
- **Alternatives**: a transparent encrypted model field (hides where plaintext appears; easy to serialize by accident); pgcrypto (key would live in SQL and could end up in DB query logs).
- **Guard**: `GitHubAccount.__repr__`/`__str__` exclude the token. Serializers use an explicit field allowlist. A logging filter redacts `access_token=`, `code=` and `client_secret=` patterns as a backstop.

### D3. Sessions: Django server-side sessions, same-origin SPA
- **Choice**: `SessionAuthentication` only. Session engine `cached_db` (Redis + Postgres). `SESSION_COOKIE_HTTPONLY=True`, `SameSite=Lax`, `Secure` in production, `SESSION_COOKIE_AGE` configurable (default 14 days). Call `cycle_key()` on login.
- **Same-origin**: in development, Vite proxies `/api` to Django, so the browser sees one origin. In production a reverse proxy serves both. CORS stays locked to the configured origins via `django-cors-headers` as defence in depth.
- **Why**: Stops XSS from reading tokens, uses Django's CSRF protection as-is, and needs no refresh-token logic.
- **Alternatives**: JWT in localStorage (readable by XSS; SRS wants HTTP-only cookies); JWT in cookies (reinvents sessions and makes revocation harder).
- **CSRF**: `GET /api/v1/auth/csrf/` sets the cookie (`ensure_csrf_cookie`). The frontend reads `csrftoken` and sends `X-CSRFToken`. OAuth callback is a GET and is protected by `state`.

### D4. Custom User model from day one
- **Choice**: `accounts.User(AbstractUser)`, with `AUTH_USER_MODEL` set before the first migration. Users have unusable passwords, and username is set to `gh_<github_id>` so it's stable if the GitHub login is renamed.
- **Why**: Swapping the user model after migrations is very painful. GitHub identity lives on `GitHubAccount` (OneToOne), kept separate from profile data (SRS-2 §43).

### D5. Disconnect ordering
Revoke with GitHub (`DELETE /applications/{client_id}/grant`, basic auth with client credentials, body `{access_token}`, 10s timeout) **→** delete `GitHubAccount` **→** audit **→** `logout()`. Local deletion runs in a `finally` path so a GitHub outage can't leave a token behind. Revocation runs synchronously (a single call with a timeout) so the user gets a definite result. The User row is kept. Removing it is FR-DATA-003.

### D6. API conventions
- URL root `config/urls.py` mounts `api/v1/` → each app's `urls.py`.
- DRF defaults: `IsAuthenticated`, `SessionAuthentication`, `PageNumberPagination`, custom `EXCEPTION_HANDLER` in `config/exceptions.py` that produces `{"error": {code, message, details}}`, mapping DRF `NotAuthenticated → not_authenticated`, `Throttled → throttled`, `ValidationError → validation_error`, and CSRF failures → `csrf_failed`.
- Throttles: `AnonRateThrottle`, `UserRateThrottle` and a scoped `auth` throttle on sign-in endpoints. Rates are set in settings.
- `drf-spectacular` serves `/api/v1/schema/`. The schema is committed at `apps/frontend/src/api/openapi.json`. `openapi-typescript` generates `src/api/schema.d.ts`. CI regenerates both and fails if `git diff` isn't empty.
- Security headers via `SecurityMiddleware` settings (`SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=DENY`, `SECURE_REFERRER_POLICY=same-origin`, and in production `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*`).

### D7. Tooling
- **Python**: `uv` with `pyproject.toml` and `uv.lock` in `apps/backend`. ruff (lint + format), mypy with `django-stubs`/`djangorestframework-stubs`, pytest-django. Settings module picked with `DJANGO_SETTINGS_MODULE` (`config.settings.development` by default, `config.settings.test` for pytest).
- **Frontend**: npm, Vite, React 19, TS strict, Tailwind v4 + shadcn/ui, TanStack Query, React Router, Vitest + RTL, ESLint flat config + Prettier.
- **Docker**: `pgvector/pgvector:pg16` so Phase 6 needs no image change, `redis:7-alpine`, and one backend image reused for `backend`, `worker` and `beat` with different commands. Postgres and Redis get healthchecks, and the backend waits for them.
- **Celery**: `config/celery.py` with autodiscovery and a `core.tasks.ping` task that proves the worker runs. Tests use `CELERY_TASK_ALWAYS_EAGER`.

### D8. Audit log
`accounts.AuditEvent(user FK nullable, action, outcome, metadata JSON, ip_hash, created_at)`, written by `services/audit.record(...)`. Metadata keys are allowlisted so credentials can't be stored by mistake. The IP is hashed with a server salt instead of stored raw.

### D9. Local mode without Docker (`npm start`)
- **Context**: the primary dev machine (Windows) has PostgreSQL 18 installed natively but no Docker and no Redis.
- **Choice**: a root `package.json`. `npm run setup` creates `.env` with generated secrets, installs backend (uv) and frontend (npm) deps, and migrates. `npm start` runs `migrate` + `runserver :8000` and Vite `:5173` together through `concurrently`. `scripts/uv.mjs` finds `uv` either on PATH or as `python -m uv`.
- **Database**: `DATABASE_URL` defaults to the local `contribfinder` role/database on `localhost:5432`. Tests run against the same server (pytest creates `test_contribfinder`, which needs `CREATEDB`).
- **No Redis**: when `REDIS_URL` is empty, the cache is in-process (LocMem), Celery runs tasks inline (`task_always_eager`, `memory://` broker), and health reports Redis as `not_configured` (HTTP 200). Production settings refuse to start without `REDIS_URL`.
- **Docker unchanged**: compose sets its own `DATABASE_URL`/`REDIS_URL` with container hostnames, so one `.env` works for both modes.
- **Alternatives**: SQLite fallback (rejected: differs from production Postgres, hides real DB behaviour); requiring Redis locally (rejected: no native Windows Redis build; Memurai/WSL is extra setup for Phase 1, which has no background jobs).
- **Limit**: throttle counters and sessions in LocMem are per-process, which is fine for a single dev server. Phase 2 sync jobs will need Redis (or Memurai/WSL) to exercise real async behaviour.

## Risks / Trade-offs

- [Hand-rolled OAuth has subtle bugs (state reuse, open redirect)] → The post-login redirect target is a fixed frontend route from settings, never a query parameter. Tests cover state missing, reused and mismatched, `error=access_denied`, and token exchange failure.
- [Losing `TOKEN_ENCRYPTION_KEYS` makes stored tokens unreadable] → Users just sign in again (tokens are re-obtainable). Document key management in `.env.example`. MultiFernet allows rotation.
- [Revocation call adds latency to disconnect] → 10s timeout. Local deletion still happens on failure.
- [Committed OpenAPI schema causes merge conflicts] → The file is generated, and CI tells contributors to regenerate it. This is worth it to catch contract drift.
- [Same-origin assumption breaks if the frontend is hosted on a different domain (e.g. Vercel)] → Production must put a proxy or rewrite in front so `/api` is same-site. This is recorded as a deployment constraint for a later phase.
- [Windows development environment] → Everything runs in Docker. Local non-Docker runs are optional, and `uv`/npm both work on Windows.

## Migration Plan

Greenfield, so there's no data migration. Rollout: register a GitHub OAuth App (dev callback `http://localhost:5173/api/v1/auth/github/callback` via the Vite proxy), fill `.env` from `.env.example`, run `docker compose up`, then run migrations. Rollback: revert the change. No persistent data depends on it yet.
