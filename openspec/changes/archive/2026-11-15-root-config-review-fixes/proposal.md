## Why

Review sweep of the root config (`docker-compose.yml`, `.env.example`, `package.json`), the last
module of the full review sweep. `/code-review` reported 10 findings, each checked against the
files, the settings modules and the runners (ROOT-1…ROOT-10 in `Bug_Backlog.md`, batch 70).
`/security-review` found nothing at its bar. Docker mode does publish a `DEBUG=True` dev server on
all interfaces, but the API needs a session and never returns tracebacks, the admin has no
usable account, and debug pages mask secrets. So it is hardening, and it is fixed here as ROOT-1.
Its note that Vite also listens on all interfaces in `npm start` is recorded as accepted:
`host: true` is kept for phone testing on the LAN.

Docker mode is "kept, not used here" (CLAUDE.md §6), so these fixes keep it safe and working
without touching the primary `npm start` flow. The exception is ROOT-3: the Redis container's
host port collides with the WSL Redis that `npm start` uses.

## What Changes

- **ROOT-1, ROOT-2** The backend is published as `127.0.0.1:8000:8000` and the frontend as
  `127.0.0.1:5173:5173`. With only the loopback interface published, the `X-Forwarded-For` spoofing
  that needs a direct LAN path goes too.
- **ROOT-3** The Redis service drops `ports`: containers reach it as `redis:6379`.
- **ROOT-4** README (Docker section): rebuild with `docker compose up --build --renew-anon-volumes`
  after a frontend dependency change. A comment in the compose file at the `node_modules` volume
  says the same.
- **ROOT-5** `vite.config.ts` reads `watch.usePolling` from `VITE_WATCH_POLLING=true`, which only
  the compose file sets.
- **ROOT-6** `development.py` reads `DEBUG = env.bool("DJANGO_DEBUG", default=True)`. Production
  still forces `False`. The `.env.example` comment says it applies to development only.
- **ROOT-7** `.env.example` lists the 17 missing settings with their defaults: `SECURE_SSL_REDIRECT`,
  `THROTTLE_ANON/USER/AUTH`, `SESSION_COOKIE_AGE`, `DB_CONN_MAX_AGE`, `LOG_LEVEL`,
  `GITHUB_SYNC_MAX_REPOS`, `GITHUB_MAX_PAGES`, `GITHUB_HTTP_TIMEOUT`, `GITHUB_MAX_RETRY_DELAY`,
  `GITHUB_ETAG_TTL`, `SYNC_MAX_ATTEMPTS`, `SYNC_COOLDOWN_SECONDS`, `OAUTH_STATE_TTL_SECONDS`,
  `OAUTH_STATE_MAX_PENDING`. A backend test compares the settings' `env*()` names with the
  template, ignoring the test-only `DJANGO_READ_DOTENV`.
- **ROOT-8** The compose `environment` drops `DJANGO_SETTINGS_MODULE`, so `.env` (via `env_file`)
  decides it.
- **ROOT-9** The Postgres credentials are defined once (`x-postgres` anchor for the service env).
  The healthcheck uses `$$POSTGRES_USER`/`$$POSTGRES_DB`, and `DATABASE_URL` stays the one literal,
  with a comment that ties it to the anchor.
- **ROOT-10** `format:scripts:write` (`prettier --write scripts`) is added, and
  `"engines": { "node": ">=22" }`, since the runners use the `node --test` glob and
  `import.meta.dirname`. CI stays on 24.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `developer-tooling`: ADDED "Docker development mode stays local and current".

## Impact

- Files: `docker-compose.yml`, `.env.example`, `package.json` (refresh `package-lock.json`, whose
  root entry records `engines`), `apps/frontend/vite.config.ts`, `apps/backend/config/settings/development.py`,
  `README.md` (Docker section), and a new backend test (`tests/test_env_example.py`).
- `docker compose up --build` from a fresh `.env` needs a manual check: it stays a CLAUDE.md
  future item and is not part of CI.
- No API, migration or ranking change. Patch release after `shared-components-review-fixes`.
