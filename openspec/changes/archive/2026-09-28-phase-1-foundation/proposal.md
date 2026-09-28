## Why

The repository contains only the two SRS documents. Every later phase (GitHub ingestion, profiling, discovery, ranking) needs the same base: a runnable Django + React monorepo, background workers, a versioned API, and a user who is signed in with GitHub and whose token is stored safely. Building this first means later phases add features instead of rebuilding infrastructure. It also covers FR-AUTH-001..003, which the MVP needs regardless.

## What Changes

- Scaffold the monorepo: `apps/backend` (Django, DRF, Celery) and `apps/frontend` (React 19, TypeScript, Vite), with a `docker-compose.yml` that runs backend, Celery worker, Celery beat, PostgreSQL (pgvector-capable image), Redis and the frontend.
- Add split Django settings (base/development/production) driven by environment variables, a custom `User` model, and an `/api/v1/` API root with a generated OpenAPI schema and a health endpoint.
- Add a consistent JSON error envelope, API throttling, CSRF protection, secure cookie settings and security headers.
- Add GitHub OAuth sign-in: start authorization, handle the callback, create/update the local user and linked GitHub account, and start an HTTP-only session.
- Store the GitHub access token encrypted at rest. It is never returned to the client or logged.
- Add session endpoints: current user, logout.
- Add GitHub disconnect: revoke the authorization with GitHub, delete the stored token and account link, and end the session.
- Record an audit log entry for sign-in, logout and disconnect.
- Frontend: landing page with "Continue with GitHub", an auth guard, a minimal signed-in shell showing the user's GitHub identity, logout and disconnect controls, and API types generated from the OpenAPI schema.
- CI on pull requests: backend (ruff, mypy, pytest) and frontend (eslint, prettier check, tsc, vitest, build).

## Capabilities

### New Capabilities
- `github-authentication`: Signing in with GitHub, keeping the session, logging out, disconnecting GitHub, and handling the GitHub credential securely (FR-AUTH-001, FR-AUTH-002, FR-AUTH-003).
- `api-platform`: Cross-cutting API behaviour every later capability relies on: versioned base path, OpenAPI schema, health check, error format, authentication and CSRF enforcement, throttling and security headers.

### Modified Capabilities
<!-- None: no existing specs. -->

## Impact

- **New code**: `apps/backend/**`, `apps/frontend/**`, `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`. Update `CLAUDE.md` §6 with the real commands.
- **New dependencies**: Django, djangorestframework, django-environ, django-filter, drf-spectacular, celery, redis, psycopg, httpx, cryptography, pytest/pytest-django/factory_boy, ruff, mypy; React 19, Vite, TypeScript, TanStack Query, React Router, Tailwind, shadcn/ui, openapi-typescript, Vitest, React Testing Library.
- **External systems**: a GitHub OAuth App must be registered (client ID and secret provided through environment variables; callback URL `/api/v1/auth/github/callback`).
- **Secrets**: `DJANGO_SECRET_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` and `TOKEN_ENCRYPTION_KEYS` must be set and never committed.
