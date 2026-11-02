## Why

The review sweep's seventh module, `apps/backend/services/github/` (`Bug_Backlog.md` batch 32,
GHS-1…GHS-10), found that a sync locks shared repository rows in a different order than discovery
(deadlock), that it replaces languages and dependencies without the row lock (a concurrent
analysis makes the sync fail), that a rate-limited revocation is never retried (the grant stays
valid after disconnect), that a next-page link is checked by host only, and that a temporarily
unreadable contributed repository loses its contributor link. The security review of the module
found nothing.

## What Changes

- GHS-1: the repositories step upserts in GitHub ID order (the order of every bulk repository
  lock); which repositories are selected still follows push time.
- GHS-2: languages and dependencies are replaced under the repository row lock.
- GHS-3: a next-page link must match the API origin (scheme, host, port), like a redirect; one
  Link-header parser serves pagination and counts (GHS-10).
- GHS-4: revocation maps a 403/429 rate limit through the client's rules, so it is retried.
- GHS-5: contributions to one repository under two names are counted together.
- GHS-6: a contributed repository that is still observed but unreadable keeps its link.
- GHS-7: `httpx` decoding and URL errors become GitHub errors (transient or client), never an
  unclassified failure.
- GHS-8: response bodies larger than `GITHUB_ETAG_MAX_BYTES` are not cached.
- GHS-9: a retried dependencies step reads the set the first attempt chose.
- GHS-10: one date parser and one `API_VERSION`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-data-sync`: "Credential use during sync" (next-page links follow the redirect origin
  rule); "External contribution ingestion" (an observed but unreadable repository keeps its link;
  two names of one repository count together).

## Impact

- `apps/backend/services/github/{client,sync,oauth,storage}.py`, `config/settings/base.py`
  (`GITHUB_ETAG_MAX_BYTES`, checked by `core.E020`), tests.
- No migration, no API change (OpenAPI `1.0.0`), no ranking change, no frontend change.
