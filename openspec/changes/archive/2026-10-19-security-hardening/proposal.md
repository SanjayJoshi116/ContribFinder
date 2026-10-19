## Why

The codebase sweep (`Bug_Backlog.md`, batch 1) found verified security gaps in the platform layer.
Anyone can bypass the sign-in and anonymous rate limits by sending a random `X-Forwarded-For`
header (H-2). The log redaction backstop misses quoted secrets, the OAuth `state` and non-GitHub
`Authorization` values (H-4). The redaction filter itself can crash the code that logs (H-3). The
production defaults and deploy files also have weaknesses (H-6, H-12–H-16, G-5, G-6, A-15). These
are small, isolated fixes. They should land before any public deployment and before the larger
correctness batches.

## What Changes

- **Client identity for throttling.** Rate limits key on the connecting address. Forwarded headers
  (`X-Forwarded-For`, `X-Forwarded-Proto`) are trusted only when a new `NUM_PROXIES` setting says
  how many proxies sit in front (default 0 = trust none). **BREAKING** for any deployment behind a
  TLS-terminating proxy: it must set `NUM_PROXIES`. No such deployment exists yet.
- **Health check is not throttled**, and is exempt from the HTTPS redirect, so load-balancer probes
  are never 429 or 301.
- **Log redaction covers more forms.** It masks quoted `key='value'` reprs, `state` in dict and JSON
  forms, and any `Authorization: token|Bearer|Basic <value>`. The filter never raises into the
  caller: a malformed log call is still logged (unformatted, redacted).
- **Configuration validated at startup.** Production web and worker processes run Django system
  checks before serving and refuse to start on errors. Every serving entry point (WSGI, Celery
  worker and beat) defaults to production settings, and the backend image sets it explicitly. Only
  the developer CLI (`manage.py`) defaults to development.
- **JSON error envelope for Django-level 400 and 403** (`DisallowedHost`, oversized bodies,
  `PermissionDenied` outside DRF). Today these return HTML.
- **HSTS `includeSubDomains` and `preload` are opt-in** (`SECURE_HSTS_INCLUDE_SUBDOMAINS`,
  `SECURE_HSTS_PRELOAD`, default off). `max-age` stays configurable.
- **Sign-in from several tabs works.** The session keeps a few pending OAuth states, each single-use
  and short-lived, instead of one that the next tab overwrites.
- **Compose least exposure.** The frontend container gets only `VITE_API_PROXY_TARGET`, not the
  whole `.env` with its secrets. Redis and Postgres ports bind to `127.0.0.1` only.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-platform`: request throttling identifies clients without trusting spoofable headers; the
  health check is unthrottled and exempt from the HTTPS redirect; Django-level 400 and 403 use the
  error envelope; HSTS subdomain and preload directives are opt-in; production refuses to start
  with invalid configuration.
- `github-authentication`: several pending sign-in states per session; credential redaction
  covers quoted, `state` and generic `Authorization` forms, and logging never fails the caller.

## Impact

- Backend: `config/settings/base.py` (REST_FRAMEWORK `NUM_PROXIES`), `config/settings/production.py`
  (proxy header, redirect exemption, HSTS flags), `config/celery.py`, `config/wsgi.py`,
  `config/urls.py` + `core/views.py` (handler400 and handler403), `core/api.py` (HealthView
  throttles), `core/logging.py`, `accounts/views.py` (OAuth states), `services/audit.py` (client
  IP uses the same trusted-proxy rule).
- Deploy: `apps/backend/Dockerfile` (`DJANGO_SETTINGS_MODULE`, check before gunicorn),
  `docker-compose.yml` (frontend env, loopback ports), `.env.example` (`NUM_PROXIES`, HSTS flags).
- Tests: `test_security_primitives.py`, `test_github_auth.py`, `test_api_platform.py`, plus new
  tests for throttle identity, startup checks and error handlers.
- No API shape change; the OpenAPI schema is unchanged except the health operation, which loses its
  429 response.
- Out of scope (other batches): Redis outage turning reads into 500s (H-1, batch 5), privacy and
  deletion items (batch 2), unchecked settings such as `EXPERIENCE_THRESHOLDS` (H-7, batch 10).
