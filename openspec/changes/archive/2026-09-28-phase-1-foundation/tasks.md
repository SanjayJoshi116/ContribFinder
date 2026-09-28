## 1. Repository and environment scaffolding

- [x] 1.1 Add root `.gitignore` (Python, Node, `.env`, build output) and `.env.example` listing every required variable with safe placeholder values and comments (DJANGO_SECRET_KEY, DATABASE_URL, REDIS_URL, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_OAUTH_SCOPES, TOKEN_ENCRYPTION_KEYS, FRONTEND_URL, ALLOWED_HOSTS, CORS/CSRF trusted origins)
- [x] 1.2 Create `apps/backend` with `uv` project (`pyproject.toml`, `uv.lock`): Django, DRF, django-environ, django-filter, django-cors-headers, drf-spectacular, celery, redis, psycopg[binary], httpx, cryptography; dev: pytest, pytest-django, factory_boy, respx, ruff, mypy, django-stubs, djangorestframework-stubs
- [x] 1.3 Create `apps/frontend` with Vite React 19 + TypeScript (strict), Tailwind v4, shadcn/ui init, TanStack Query, React Router, Vitest + RTL + jsdom, ESLint flat config, Prettier, openapi-typescript; configure Vite dev proxy `/api` → backend
- [x] 1.4 Add backend Dockerfile (single image) and frontend Dockerfile (dev server)
- [x] 1.5 Add `docker-compose.yml` with `postgres` (pgvector/pgvector:pg16, healthcheck), `redis` (redis:7-alpine, healthcheck), `backend`, `worker`, `beat`, `frontend`; backend waits for healthy dependencies
- [x] 1.7 Add local (non-Docker) mode: root `package.json` with `npm run setup` / `npm start` (concurrently: Django :8000 + Vite :5173), `DATABASE_URL` default to local PostgreSQL, Redis-optional fallbacks (LocMem cache, eager Celery, health `not_configured`), production guard requiring `REDIS_URL`
- [x] 1.8 Create local PostgreSQL role/database `contribfinder` (CREATEDB for tests); run backend suite and `npm start` smoke test against it

## 2. Django project foundation

- [x] 2.1 Create `config/` with `settings/{base,development,test,production}.py` using django-environ; production enables SSL redirect, HSTS and Secure cookies
- [x] 2.2 Create `accounts` app with custom `User(AbstractUser)`, set `AUTH_USER_MODEL`, generate the initial migration before any other migration
- [x] 2.3 Create `core` and `github` apps and a `services/` package (`services/github/`, `services/crypto.py`, `services/audit.py`)
- [x] 2.4 Configure `config/celery.py` (autodiscover, Redis broker/result), add `core.tasks.ping` (verified with eager execution in tests; in-Docker worker check deferred, see below)
- [x] 2.5 Configure sessions (`cached_db`, HttpOnly, SameSite=Lax, configurable age), CSRF (cookie readable by the SPA, trusted origins), CORS allowlist, and security header settings
- [x] 2.6 Configure pytest (`config.settings.test`, eager Celery), ruff and mypy in `pyproject.toml`; add a shared factory module

## 3. API platform (spec: api-platform)

- [x] 3.1 Mount `api/v1/` in `config/urls.py` and set DRF defaults (SessionAuthentication, IsAuthenticated, pagination, throttle classes and configurable rates including a scoped `auth` throttle)
- [x] 3.2 Implement `config/exceptions.py` handler producing `{"error": {code, message, details}}` for validation, not_authenticated, permission_denied, csrf_failed, throttled (with Retry-After), not_found and server_error (no internals leaked)
- [x] 3.3 Implement `GET /api/v1/health/` (public) checking DB and Redis; 200 when both are ok, 503 with the failing dependency marked `unavailable`
- [x] 3.4 Serve `GET /api/v1/schema/` via drf-spectacular with auth and health endpoints documented, including error responses
- [x] 3.5 Tests: unknown non-prefixed path → 404; error envelope for 400/401/403/429/500; health ok and degraded; security headers present; disallowed origin gets no CORS allow header; schema endpoint returns valid OpenAPI 3

## 4. Token encryption and audit

- [x] 4.1 Implement `services/crypto.py` (`encrypt_token`, `decrypt_token`) with MultiFernet from `TOKEN_ENCRYPTION_KEYS`; fail fast at startup if keys are missing or invalid
- [x] 4.2 Create `GitHubAccount` (OneToOne User, unique `github_id`, `username`, `avatar_url`, `access_token_encrypted`, `scopes`, timestamps) with `__str__`/`__repr__` that exclude the token
- [x] 4.3 Create `AuditEvent` model and `services/audit.record(user, action, outcome, metadata, request)` with metadata key allowlist and salted IP hash
- [x] 4.4 Add a logging filter that redacts `access_token`, `code`, `client_secret` values, and attach it to all handlers
- [x] 4.5 Tests: encrypt/decrypt round trip; ciphertext ≠ plaintext; key rotation (old key decrypts, new key encrypts); audit metadata rejects unlisted keys; redaction filter masks sample log lines

## 5. GitHub sign-in (spec: github-authentication)

- [x] 5.1 Implement `services/github/oauth.py`: `build_authorize_url(state)`, `exchange_code(code) → token` (httpx, timeout, error mapping), `fetch_identity(token)`, `revoke_grant(token)`
- [x] 5.2 Implement `GET /api/v1/auth/github`: generate single-use state in session, redirect to GitHub with configured client ID, callback URL and scopes
- [x] 5.3 Implement `GET /api/v1/auth/github/callback`: handle `error` param, validate and consume state before any GitHub call, exchange code, fetch identity, upsert User (`gh_<id>`, unusable password) and GitHubAccount by `github_id`, encrypt token, `login()` with session key rotation, audit, redirect to the fixed frontend route; on failure redirect to the frontend with an error code
- [x] 5.4 Apply the scoped `auth` throttle to sign-in endpoints
- [x] 5.5 Tests (respx-mocked GitHub): first-time sign-in creates user and account; returning user updates without duplicating; missing, reused and mismatched state rejected without calling GitHub; `access_denied` handled; token exchange failure/timeout handled; stored token is encrypted; captured logs contain no token/code/secret

## 6. Session, logout, disconnect

- [x] 6.1 Implement `GET /api/v1/auth/csrf/` (sets CSRF cookie) and `GET /api/v1/auth/me` (user id, GitHub username, display name, avatar URL, `github_connected`) with an explicit serializer field allowlist
- [x] 6.2 Implement `POST /api/v1/auth/logout`: flush the session, audit, keep GitHubAccount
- [x] 6.3 Implement `POST /api/v1/auth/github/disconnect`: revoke grant (10s timeout), delete GitHubAccount in a guaranteed path, audit with revocation outcome, logout
- [x] 6.4 Tests: `/me` 200 signed in and 401 signed out; response bodies across auth endpoints never contain the token; logout invalidates the old cookie and keeps the account; POST without CSRF → 403 `csrf_failed`; disconnect success; disconnect with GitHub failure still deletes the link and ends the session; re-sign-in after disconnect re-links the same user; expired session treated as unauthenticated

## 7. Frontend

- [x] 7.1 Add an API client (`src/api/client.ts`) that sends credentials, attaches `X-CSRFToken` on mutating requests, primes CSRF via `/auth/csrf/`, and parses the error envelope into a typed error
- [x] 7.2 Commit the generated `src/api/openapi.json` and `src/api/schema.d.ts`; add `npm run gen:api` script (fetch/export schema → openapi-typescript)
- [x] 7.3 Add TanStack Query `useMe()` hook and a route guard that redirects signed-out users to the landing page
- [x] 7.4 Build the landing page ("Find Your Next OSS Contribution" + "Continue with GitHub" linking to `/api/v1/auth/github`) and show readable messages for callback error codes (cancelled, failed/retry)
- [x] 7.5 Build the signed-in shell: avatar and username, logout button, and disconnect button with a confirmation dialog explaining the effect
- [x] 7.6 Tests (Vitest + RTL): landing renders CTA; guard redirects when `/me` is 401; shell renders identity; logout and disconnect call the right endpoints with a CSRF header; error codes show messages

## 8. CI and documentation

- [x] 8.1 Add `.github/workflows/ci.yml` with backend job (uv sync, ruff check, ruff format --check, mypy, pytest with Postgres + Redis services) and frontend job (npm ci, eslint, prettier --check, tsc, vitest, build)
- [x] 8.2 Add a CI step that regenerates the OpenAPI schema and TS types and fails on `git diff`
- [x] 8.3 Update `CLAUDE.md` §6 with the real dev/test/lint/codegen commands, and correct the GitHub scope note to "no scopes (public data only)"
- [x] 8.4 Update `README.md` with setup steps: register a GitHub OAuth App (callback URL), fill `.env`, generate `TOKEN_ENCRYPTION_KEYS`, `docker compose up`, migrate
- [x] 8.5 Manual end-to-end check with a real OAuth App: sign in, see identity, log out, sign in again, disconnect, and confirm the app is gone from GitHub → Settings → Applications

## Deferred

No Docker on the development machine, so these checks move to Phase 2 (tracked in `CLAUDE.md`, Phase 2 carry-over). The Docker files are kept and were not modified beyond environment URLs.

- 1.6 Verify `docker compose up` starts every service cleanly from a fresh `.env`
- 2.4 (remainder) Confirm the Celery worker runs `core.ping` inside Docker against Redis
