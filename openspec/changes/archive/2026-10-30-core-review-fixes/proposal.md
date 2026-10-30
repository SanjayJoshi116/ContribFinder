## Why

The review sweep's second module, `apps/backend/core/` (`Bug_Backlog.md` batch 27, CORE-1…CORE-10),
found a production startup gate that blocks on checks the operator silenced, settings that pass
validation while breaking client-IP detection, discovery, every response or the refresh backlog
(`NUM_PROXIES`, all-zero query shares, a CSP with a newline, a zero stale-after), gaps in the log
redaction backstop, non-atomic report writes and check lists copied from the services. The
security review of the module found nothing exploitable.

## What Changes

- CORE-1: the startup gate ignores silenced messages at every level, as `manage.py check` does.
- CORE-5: the gate also runs Django's deployment checks; their warnings are logged (only errors
  block, as today).
- CORE-2: `NUM_PROXIES` must be a non-negative integer.
- CORE-4: `DISCOVERY_QUERY_SHARES` must have a positive total.
- CORE-6: both Content Security Policy settings must be single-line printable text.
- CORE-8: `REPO_STALE_AFTER` values must be positive.
- CORE-7: a check that reports a wrongly typed value skips its numeric comparison instead of
  crashing.
- CORE-10: the checks use `queries.STRATEGIES` and `staleness.PARTS` instead of copies.
- CORE-3: the redaction filter also masks prefixed key names (`GITHUB_CLIENT_SECRET=`,
  `encrypted_access_token=`), cookies (`sessionid`, `csrftoken`), `password`, `secret` and
  `TOKEN_ENCRYPTION_KEYS` values.
- CORE-9: `write_json` writes to a temporary file in the same folder and replaces the target
  atomically; serialization errors become the same `CommandError`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-platform`: "Configuration validated at startup" covers silenced checks, deployment
  checks, `NUM_PROXIES`, the query shares' total, the Content Security Policy text, positive
  stale-after windows, and wrongly typed values reported instead of crashing validation.

## Impact

- `apps/backend/core/{startup,checks,logging,reports}.py`, tests.
- No API, model, migration or frontend change; baselines unchanged.
