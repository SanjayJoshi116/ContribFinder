## Why

The full review sweep's first module, `apps/backend/config/` (`Bug_Backlog.md` batch 26), found
settings that let local tests drift from CI, a Celery publish without a read timeout (an HTTP
request can hang on a stalled Redis, against invariant 3), unchecked pooled database
connections, JSON settings that crash startup without naming themselves, a `LOG_LEVEL` that
Django's logger ignores, and smaller inconsistencies. The security review of the module found
nothing.

## What Changes

- CFG-1: the test settings take only `DATABASE_URL` from the repo-root `.env`
  (`DJANGO_READ_DOTENV=DATABASE_URL`, parsed in `base.py` by django-environ), so local pytest
  sees CI's settings.
- CFG-2: the Celery broker gets `socket_timeout` (`REDIS_SOCKET_TIMEOUT`) beside the connect
  timeout.
- CFG-3: `CONN_HEALTH_CHECKS = True` with persistent database connections.
- CFG-4: `env_json` and `env_mapping` helpers: invalid JSON, or a non-object for the eight
  object settings, raises `ImproperlyConfigured` naming the setting.
- CFG-5: `visibility_timeout` set above the longest retry delay (at least the 3600 s default).
- CFG-6: an `APIException` with a dict or list detail keeps its default message and puts the
  detail in `details`, never a Python repr in `message`.
- CFG-9: `LOG_LEVEL` sets the `django` logger as well as the root logger.
- CFG-10: `GITHUB_OAUTH_SCOPES` accepts commas as well as spaces.
- CFG-7 accepted (revisit with error tracking, `ideas.md` §5). CFG-8 accepted: at startup
  `base` and `production` read the same environment, and the production-settings tests rely on
  `production.py` reading it (they set `REDIS_URL` after `base` is imported).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None (`skip_specs`): the code follows the existing specs; no specified behavior changes.

## Impact

- `apps/backend/config/settings/{base,test}.py`, `config/exceptions.py`, tests.
- No API, model, migration or frontend change; baselines unchanged.
