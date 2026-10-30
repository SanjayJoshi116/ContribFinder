## Context

Batch 27 of `Bug_Backlog.md` (CORE-1…CORE-10). All fixes stay inside `core/`; the services keep
their behavior. The security review of the module found nothing.

## Decisions

### D1. Silenced means silenced (CORE-1, CORE-5)

`run_startup_checks` drops `is_silenced()` messages first, then blocks on serious ones and logs
the rest, matching `manage.py check`. It runs with `include_deployment_checks=True`; Django's
deployment checks are warnings (`security.W0xx`), so they are logged, not blocking. An operator
who wants one quiet adds it to `SILENCED_SYSTEM_CHECKS`.

### D2. New rules use the existing helpers (CORE-2, CORE-4, CORE-6, CORE-8)

`NUM_PROXIES` joins `NON_NEGATIVE_INT_SETTINGS` (`core.E050`). `REPO_STALE_AFTER` values use the
positive-integer item rule of `_keys_errors`. The query shares keep their per-key rule plus a
positive total (`core.E022`). CSP values must contain no control character (`core.E060`): Django
refuses such header values.

### D3. Checks never crash on a reported value (CORE-7)

Each numeric comparison runs only when the value passed its type test (`_is_int` or a number
test), so a bad override yields its configuration error, not a `TypeError`.

### D4. One source for keys (CORE-10)

The strategies and stale parts are read from `services.discovery.queries.STRATEGIES` and
`services.repositories.staleness.PARTS` inside the check functions (lazy import, as
`configured_star_bands` already is), so `core/checks.py` imports no app code at load time.

### D5. Redaction keys match inside names (CORE-3)

Key patterns match when the key ends a longer name (`[A-Za-z0-9_]*` before it), so
`GITHUB_CLIENT_SECRET=x` and `encrypted_access_token='x'` are masked. Keys add `secret`,
`password`, `sessionid`, `csrftoken`, `encryption_keys`. Over-masking a harmless value
(`zipcode=`) is acceptable for a backstop.

### D6. Atomic report writes (CORE-9)

`write_json` serializes first (a `TypeError` or `ValueError` becomes `CommandError` before any
file is touched), writes a temporary file in the target's folder and `os.replace`s it; the
temporary file is removed on failure.

## Risks / Trade-offs

- Deployment checks may log new warnings on existing deployments; they do not block.
- Broader redaction may mask non-secret values in logs; acceptable for a backstop.
