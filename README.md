# ContribFinder

Finds open-source repositories and issues that match a developer's demonstrated skills and
interests. It builds an evidence-backed profile from GitHub and explains every recommendation.

**Version 0.3.0** (Phase 3: Developer profile). After signing in with GitHub, your public
profile, README, repositories, dependencies and contributions are synced in the background and
turned into an evidence-backed profile: skills (with the evidence behind each), interests and
languages. Repository discovery and recommendations are next.

- Stack: Django + DRF + Celery + PostgreSQL (+ Redis), React 19 + TypeScript + Vite.
- What's shipped and planned: [`features.txt`](features.txt). Release notes: [`CHANGELOG.md`](CHANGELOG.md).
- Requirements: `Software Requirements Specification - 2.txt` (authoritative) and `- 1.txt`.
- Engineering guide and roadmap: [`CLAUDE.md`](CLAUDE.md). Specs: `openspec/specs/`; archived
  changes: `openspec/changes/archive/`.

## 1. Register a GitHub OAuth App

GitHub → Settings → Developer settings → OAuth Apps → **New OAuth App**

| Field | Value |
|---|---|
| Homepage URL | `http://localhost:5173` |
| Authorization callback URL | `http://localhost:5173/api/v1/auth/github/callback` |

Copy the **Client ID** and generate a **Client secret**. ContribFinder requests no OAuth scopes;
it reads public data only.

## 2a. Run locally (no Docker)

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/) (`python -m pip install uv` works too; it
doesn't need to be on PATH, and you can set `UV_BIN` to point at it),
Node 24, a local PostgreSQL and, for background jobs, Redis. On Windows, Redis runs inside WSL
(Ubuntu); `npm start` starts it for you. Without Redis the cache is in-process and background
tasks run inline, so GitHub syncs block the request.

Create the database once. `psql` prompts for the `postgres` password:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -c "CREATE ROLE contribfinder LOGIN PASSWORD 'contribfinder' CREATEDB;" -c "CREATE DATABASE contribfinder OWNER contribfinder;"
```

`CREATEDB` lets the test suite create its own `test_contribfinder` database.

Install Redis in WSL once (runs as root, so no sudo password is needed):

```powershell
wsl -d Ubuntu -u root -- apt-get install -y redis-server
```

ContribFinder uses Redis database 1 (`REDIS_URL=redis://localhost:6379/1`), so it doesn't touch
anything else stored in that Redis.

Then:

```bash
npm install        # root: installs the dev runner
npm run setup      # creates .env with generated secrets, installs deps, runs migrations
```

Add `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` from step 1 to `.env`, then:

```bash
npm start          # WSL Redis + Django :8000 + Celery worker + Vite :5173 (proxies /api)
```

Open http://localhost:5173. API health: http://localhost:5173/api/v1/health/.

Django management commands work from the root without uv on PATH:

```bash
npm run manage -- migrate
npm run manage -- reanalyze_profiles   # rebuild profiles from stored data (no GitHub calls)
```

Profile scoring is configurable in `.env` (`EVIDENCE_WEIGHTS` and friends, see `.env.example`).
Run `reanalyze_profiles` after changing it.

## 2b. Run with Docker

```bash
cp .env.example .env    # or reuse the .env from `npm run setup`
docker compose up --build
```

Compose runs its own Postgres (host port 5433) and Redis, and overrides `DATABASE_URL` and
`REDIS_URL` with container hostnames, so the same `.env` works for both modes. If you copied
`.env.example`, fill in `DJANGO_SECRET_KEY` and `TOKEN_ENCRYPTION_KEYS` yourself (commands
are in the file).

## Secrets

`TOKEN_ENCRYPTION_KEYS` encrypts stored GitHub tokens. To rotate, put a new key first
(`new,old`); old tokens still decrypt. If every key is lost, users just sign in again.
Never commit `.env`.

## Tests

`uv run pytest` in `apps/backend` (uses local PostgreSQL) and `npm test` in `apps/frontend`.
All commands are in `CLAUDE.md` §6.

## Versioning

`VERSION` is the single source of truth. Keep `package.json`, `apps/frontend/package.json` and
`apps/backend/pyproject.toml` in sync; `npm run check:version` (also run in CI) verifies it.
Before the MVP, each completed roadmap phase bumps the minor version.
