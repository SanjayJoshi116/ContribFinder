## Context

Findings and verdicts are in `Bug_Backlog.md` (batch 70, ROOT-1…ROOT-10). Relevant facts:

- Compose publishes `8000:8000` and `5173:5173` on all interfaces. Postgres is published on
  `127.0.0.1:5433` and Redis on `127.0.0.1:6379`. `REDIS_URL` in `.env` is `localhost:6379/1` for
  the WSL Redis.
- `DJANGO_SETTINGS_MODULE: ${DJANGO_SETTINGS_MODULE:-config.settings.development}`: compose
  interpolation prefers the shell over the project `.env`.
- `base.py` reads `DJANGO_DEBUG`, but `development.py` sets `DEBUG = True` and `production.py`
  sets `DEBUG = False`.
- `vite.config.ts`: `server.host: true`, no `watch` options.
- The CI Node version is 24. The runners use `node --test` with a glob (Node 21+) and
  `import.meta.dirname` (Node 20.11+).

## Goals / Non-Goals

**Goals:** a safe and working Docker dev mode, a complete env template, and no change to
`npm start` behavior.

**Non-Goals:** a production compose file; running `docker compose up` in CI; binding Vite to
localhost in `npm start` (accepted: LAN phone testing).

## Decisions

### D1. Loopback ports (ROOT-1, ROOT-2, ROOT-3)

`"127.0.0.1:8000:8000"`, `"127.0.0.1:5173:5173"`. Redis gets no `ports`. Inside the containers
Vite still binds `0.0.0.0` (needed for Docker port forwarding). The proxy target stays
`http://backend:8000`.

### D2. Settings module and debug (ROOT-6, ROOT-8)

Remove the `DJANGO_SETTINGS_MODULE` line from compose `environment`; `env_file: .env` supplies
it, and `npm run setup` writes `config.settings.development`. In `development.py`:
`DEBUG = env.bool("DJANGO_DEBUG", default=True)` (it imports `env` from `base`). `production.py`
is unchanged.

### D3. Env template test (ROOT-7)

`tests/test_env_example.py` collects the names passed to `env(...)`, `env.bool/int/float/str`,
`env_list`, `env_json` and `env_mapping` in `config/settings/base.py` and `production.py`. It uses
`ast` and string first arguments only. It asserts that each name appears in `.env.example` as
`NAME=` or `# NAME=`, with an allow-list `{"DJANGO_READ_DOTENV"}`.

### D4. Watch polling and rebuilds (ROOT-4, ROOT-5)

`server.watch = process.env.VITE_WATCH_POLLING === 'true' ? { usePolling: true, interval: 300 } :
undefined`. Compose sets `VITE_WATCH_POLLING: "true"` on the frontend. README: a Docker note on
`--renew-anon-volumes`.

### D5. Compose credentials and npm (ROOT-9, ROOT-10)

```yaml
x-postgres-env: &postgres-env
  POSTGRES_DB: contribfinder
  POSTGRES_USER: contribfinder
  POSTGRES_PASSWORD: contribfinder
```

The healthcheck becomes `pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"`. `package.json`
gets `"format:scripts:write"` and `"engines": { "node": ">=22" }`. `check:version` is unaffected.
