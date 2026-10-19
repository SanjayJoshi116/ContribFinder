## Context

See proposal.md for motivation; the defects are rows H-2, H-3, H-4, H-6, H-12–H-16, G-5, G-6 and
A-15 in `Bug_Backlog.md` (verified, with corrected locations).

Current state that shapes the approach:
- DRF throttles are global defaults (`REST_FRAMEWORK` in `config/settings/base.py`). With
  `NUM_PROXIES` unset, DRF's `get_ident` uses the whole `X-Forwarded-For` header as the identity.
- `production.py` trusts `X-Forwarded-Proto` unconditionally and hard-codes HSTS
  `includeSubDomains`/`preload`.
- In development the SPA reaches Django through the Vite proxy, which adds `X-Forwarded-For`
  (`xfwd: true`), so locally there is exactly one trusted proxy.
- `services/audit.py` hashes `REMOTE_ADDR`, so behind a proxy every audit entry would get the
  proxy's address.
- `wsgi.py` defaults to production settings; `config/celery.py` and `manage.py` default to
  development. The npm runners load `.env`, which sets `DJANGO_SETTINGS_MODULE`. The backend image
  sets nothing and runs gunicorn.
- System checks (`core/checks.py`, registered in `core/apps.py`) run only for management commands
  (`check`, `migrate`, `runserver`), never under gunicorn or Celery.
- `RedactSecretsFilter` calls `record.getMessage()` inside `Filter.filter`, which runs before the
  handler's `emit`/`handleError` guard.

## Goals / Non-Goals

**Goals:**
- One setting decides which forwarded headers are trusted, and every place that needs the client
  address or protocol (throttles, HTTPS detection, audit IP) follows it.
- Startup validation that covers every production process, not only the image's CMD.
- Keep local development working without new steps for existing `.env` files.

**Non-Goals:**
- Making Redis optional for throttling and sessions (H-1; batch 5).
- New checks for settings that have none today (H-7; batch 10). This change only makes the
  existing checks run at startup.
- Privacy items such as audit metadata or `display_name` (batch 2).

## Decisions

### D1. `NUM_PROXIES` is the single trust switch
A new env setting `NUM_PROXIES` (int, default `0`) drives three things:
- `REST_FRAMEWORK["NUM_PROXIES"]`: with 0, DRF ignores `X-Forwarded-For` and uses `REMOTE_ADDR`.
  With N > 0, it takes the Nth address from the right, which the client cannot choose.
- `SECURE_PROXY_SSL_HEADER` is set in `production.py` only when `NUM_PROXIES > 0`.
- The audit client IP uses the same rule through one shared helper (`core/net.py`, `client_ip`),
  so audit hashes and throttling agree.

`.env.example` sets `NUM_PROXIES=1` with a comment that it is for the Vite dev proxy. Existing local
`.env` files without the variable fall back to 0. All local anonymous traffic then shares
`127.0.0.1`, which is harmless for one developer.

*Alternatives:* a middleware that rewrites `REMOTE_ADDR` (as django-xff does) adds a dependency and
mutates request META for all code. Separate settings for throttling and HTTPS detection could
disagree. Both rejected.

A production system check warns (Warning, not Error) when `SECURE_SSL_REDIRECT` is on and
`NUM_PROXIES` is 0. That combination behind a TLS-terminating proxy redirects in a loop. It is
legitimate only when gunicorn terminates TLS itself, so it is not an error.

### D2. Health check: no throttles, exempt from the HTTPS redirect
`HealthView.throttle_classes = []` and `SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]`. The health
handler does two cheap pings, so dropping the throttle does not open a meaningful load vector. The
OpenAPI operation drops its 429 response, so `npm run api:sync` regenerates the frontend types.

### D3. Redaction: wider patterns, fail-safe filter
Patterns in `core/logging.py`:
- `key=value` accepts an optional opening quote and masks up to the matching quote, covering
  `client_secret='…'` and `access_token="…"`.
- The JSON/dict rule adds `state` to its key list.
- An `Authorization` rule masks the value after `Authorization:` whatever its scheme (`token`,
  `Bearer`, `Basic`) or format. The existing `Bearer|Basic` rule stays for values without the
  header name.

The filter wraps `record.getMessage()` in `try/except Exception`. On failure it builds the message
from `str(record.msg)` plus `repr(record.args)`, redacts that, and still returns `True`. A
malformed call is logged, masked, and never raises into the caller.

*Alternative:* do the redaction in a `Formatter` subclass, which runs inside `emit`'s guard. Rejected
because every handler would need the formatter, and the filter also clears `args` for handlers
that format differently.

### D4. Startup validation for every production process
A helper `core/startup.py: run_startup_checks()` calls `django.core.checks.run_checks()` and raises
`SystemCheckError` listing every message at level ERROR or above. Warnings are logged. Callers:
- `config/wsgi.py`: after `get_wsgi_application()`.
- `config/celery.py`: `worker_init` and `beat_init` signal handlers.

It runs only when the `RUN_STARTUP_CHECKS` setting is true. `production.py` sets it; base,
development and test leave it false, so tests and local runs keep their current behavior.

*Alternative:* `manage.py check --fail-level ERROR && gunicorn …` in the Dockerfile CMD. Rejected as
the only mechanism because it covers gunicorn in that image only, not workers or other hosts. The
image still runs it implicitly through the WSGI hook.

### D5. One default settings module for serving tiers
`config/celery.py` defaults to `config.settings.production`, like `wsgi.py`. `manage.py` keeps
development: it is the developer CLI, and production one-off commands run inside the image, which
now sets `ENV DJANGO_SETTINGS_MODULE=config.settings.production`. Compose already overrides the
variable for its services.

The npm runners (`worker.mjs`, `beat.mjs`, `backend.mjs`) set
`DJANGO_SETTINGS_MODULE ??= 'config.settings.development'` after `loadEnv()`, so a local `.env`
without the variable never starts a production worker.

### D6. JSON handlers for framework-level 400 and 403
`handler400` and `handler403` in `core/views.py` return the envelope with codes `bad_request` and
`permission_denied`, next to the existing 404/500 handlers. DRF responses are unaffected; its
exception handler already produces the envelope.

### D7. HSTS directives opt-in
`SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD` become `env.bool(..., default=False)`.
`SECURE_HSTS_SECONDS` stays as is.

### D8. Several pending OAuth states per session
The session stores `{state: issued_at}` under a new key, `github_oauth_states`:
- Login start prunes expired entries, adds the new state and keeps the newest
  `OAUTH_STATE_MAX_PENDING` (5).
- The callback prunes expired entries (`OAUTH_STATE_TTL_SECONDS`, 600), then removes the received
  state if present. A missing entry is a state mismatch, so the existing `invalid_state` path
  applies. Removing a state leaves the other tabs' states valid.
- The old single-value key is ignored and removed. A session caught mid-sign-in during the deploy
  just gets `invalid_state` once.

Membership is a dict lookup. States are 256-bit random values, so lookup timing reveals nothing
useful. Both limits are settings, per the project rule that tunables are configuration.

### D9. Compose least exposure
The frontend service drops `env_file` and keeps only `VITE_API_PROXY_TARGET`. The Redis and Postgres
port mappings bind `127.0.0.1`. Backend and frontend ports stay as they are; they are the dev
entry points.

## Risks / Trade-offs

- [A deployment behind a proxy forgets `NUM_PROXIES`] → all users share the proxy's throttle bucket
  (mass 429), and HTTPS detection fails (redirect loop). Mitigation: the D1 system check warning,
  plus `.env.example` and README notes. No such deployment exists yet.
- [`NUM_PROXIES` set too high] → the client's own prepended value is used again. Mitigation:
  document "number of proxies you control", with a test for N=1 and a prepended value.
- [Startup checks slow down process start] → checks run once per process and take milliseconds.
- [Wider redaction masks harmless text, e.g. a log about the word `state=`] → acceptable for a
  backstop. Messages lose a value, never a whole line.
- [Changing celery's default could start a production worker locally] → D5 runner defaults close
  it, with a test that `worker.mjs` sets the variable.

## Migration Plan

1. Ship code, `.env.example` (`NUM_PROXIES=1` for dev; HSTS flags commented out) and README notes.
2. Existing local `.env` files keep working unchanged. Adding `NUM_PROXIES=1` restores per-client
   throttling locally.
3. Run `npm run api:sync` and commit the regenerated schema (the health operation loses 429).
4. Rollback: revert the commit. There are no data or migration changes.
