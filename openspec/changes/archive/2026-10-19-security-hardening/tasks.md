## 1. Trusted proxies and client identity (H-2, H-15)

- [x] 1.1 Add `NUM_PROXIES = env.int("NUM_PROXIES", default=0)` to `config/settings/base.py` and pass it as `REST_FRAMEWORK["NUM_PROXIES"]`
- [x] 1.2 Add `core/net.py` with `client_ip(request)` applying the same rule as DRF (`REMOTE_ADDR` when 0, Nth-from-right `X-Forwarded-For` entry when N > 0); use it in `services/audit.py`
- [x] 1.3 In `config/settings/production.py`, set `SECURE_PROXY_SSL_HEADER` only when `NUM_PROXIES > 0`
- [x] 1.4 Add a system check warning when `SECURE_SSL_REDIRECT` is on and `NUM_PROXIES == 0` (production settings only)
- [x] 1.5 Tests: random `X-Forwarded-For` per request with `NUM_PROXIES=0` still hits 429 on the auth scope; with `NUM_PROXIES=1` a client-prepended value is ignored; `client_ip` cases; audit IP hash follows `client_ip`; forwarded proto is untrusted with 0 proxies

## 2. Health check (H-14, H-15)

- [x] 2.1 Set `throttle_classes = []` on `HealthView` and drop 429 from its schema responses
- [x] 2.2 Add `SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]` in `production.py`
- [x] 2.3 Tests: more requests than the anonymous rate never return 429 on health; with the SSL redirect on, plain-HTTP health returns 200/503, not 301
- [x] 2.4 Run `npm run api:sync` and commit `schema` + `src/api/schema.d.ts`

## 3. Log redaction (H-3, H-4)

- [x] 3.1 Extend `core/logging.py` patterns: quoted `key='…'`/`key="…"` values, `state` in the JSON/dict rule, any `Authorization:` header value regardless of scheme or format
- [x] 3.2 Make `RedactSecretsFilter.filter` fail-safe: on a `getMessage()` exception, build the message from `str(record.msg)` and `repr(record.args)`, redact it, clear args, return `True`
- [x] 3.3 Tests: add parametrized cases for `client_secret='…'`, `access_token="…"`, `{'state': '…'}`, `Authorization: token <non-gh value>`; a malformed call (`logger.warning("%s %s", 1)`) through a handler with the filter returns normally and emits a masked line

## 4. Startup validation and settings defaults (H-6, H-12)

- [x] 4.1 Add `core/startup.py: run_startup_checks()` that runs Django system checks, logs warnings and raises `SystemCheckError` on any ERROR-level message; gate it on `settings.RUN_STARTUP_CHECKS` (false in base, true in `production.py`)
- [x] 4.2 Call it from `config/wsgi.py` after `get_wsgi_application()`, and from `worker_init` and `beat_init` signal handlers in `config/celery.py`
- [x] 4.3 Change the `config/celery.py` default settings module to `config.settings.production`; leave `manage.py` on development
- [x] 4.4 In `scripts/worker.mjs` and `scripts/beat.mjs` (`backend.mjs` runs `manage.py`, which keeps development), set `DJANGO_SETTINGS_MODULE ??= 'config.settings.development'` after `loadEnv()`
- [x] 4.5 Add `ENV DJANGO_SETTINGS_MODULE=config.settings.production` to `apps/backend/Dockerfile`
- [x] 4.6 Tests: with `RUN_STARTUP_CHECKS` true and an invalid setting (e.g. empty `TOKEN_ENCRYPTION_KEYS`), `run_startup_checks()` raises and names the check; with valid settings it passes; with the flag false it does nothing; the worker/beat signal handlers call it

## 5. Error envelope for framework-level errors (H-13)

- [x] 5.1 Add `bad_request` and `permission_denied` views to `core/views.py`; register `handler400` and `handler403` in `config/urls.py`
- [x] 5.2 Tests (DEBUG off): a disallowed `Host` returns 400 JSON with `error.code == "bad_request"`; `PermissionDenied` raised from a plain Django view returns 403 JSON `permission_denied`

## 6. HSTS directives (H-16)

- [x] 6.1 Make `SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD` `env.bool(..., default=False)` in `production.py`
- [x] 6.2 Test: with production-style settings and defaults, the HSTS header has `max-age` but no `includeSubDomains` or `preload`

## 7. Several pending OAuth states (A-15)

- [x] 7.1 Add settings `OAUTH_STATE_TTL_SECONDS` (600) and `OAUTH_STATE_MAX_PENDING` (5)
- [x] 7.2 In `accounts/views.py`, store states as `{state: issued_at}` under `github_oauth_states`: start prunes expired entries, adds the new state and keeps the newest N; callback prunes expired entries and pops the received state (missing = `invalid_state`); drop the legacy single-value key
- [x] 7.3 Update `tests/test_github_auth.py` for the new key; add tests for two tabs (first tab completes, its state is single-use, the second stays valid), expiry → `invalid_state` without a token exchange, and the cap keeping only the newest states

## 8. Compose and environment files (G-5, G-6)

- [x] 8.1 `docker-compose.yml`: remove `env_file` from `frontend` (keep `VITE_API_PROXY_TARGET`); bind Redis and Postgres ports to `127.0.0.1`
- [x] 8.2 `.env.example`: add `NUM_PROXIES=1` with a note that it covers the Vite dev proxy; add commented `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `SECURE_HSTS_PRELOAD`
- [x] 8.3 README: document `NUM_PROXIES` for deployments behind a proxy, and the startup validation

## 9. Verification and housekeeping

- [x] 9.1 Backend: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`
- [x] 9.2 Frontend: `npm run typecheck`, `npm test`, `npm run lint` (schema change only)
- [x] 9.3 Manual: `npm start` still starts web, worker and beat locally; sign-in works; two-tab sign-in works
- [x] 9.4 Mark H-2, H-3, H-4, H-6, H-12, H-13, H-14, H-15, H-16, G-5, G-6 and A-15 `fixed` in `Bug_Backlog.md`; add a CHANGELOG `[Unreleased]` entry
