## Why

The review sweep's eighth module, `apps/frontend/src/api/` (`Bug_Backlog.md` batch 33,
API-1…API-9), found that `apiFetch` does not always throw `ApiError`: a network failure or a
2xx body that is not JSON escapes as `TypeError`/`SyntaxError`, so hooks typed with `ApiError`
read an undefined status and code, and a deterministic bad body is retried as if it were a
network error. The CSRF prelude also hides the server's status, is fetched once per concurrent
mutation, and is not `keepalive` for the fire-and-forget feedback event. The security review of
the module found nothing.

## What Changes

- API-1: every `apiFetch` failure is an `ApiError`: no response → `ApiError(0, 'network_error')`,
  an unreadable 2xx body → `ApiError(status, 'invalid_response')`. Only the first is retried.
- API-2: an error without the JSON envelope keeps `retryAfter`.
- API-3: a failed `GET /auth/csrf/` raises its own `ApiError` (status, envelope), not
  `csrf_unavailable` with status 0.
- API-4: concurrent mutations share one in-flight `/auth/csrf/` request.
- API-5: a `keepalive` request sends its CSRF prelude with `keepalive` too.
- API-9: `apiFetch(path, { json })` sets `Content-Type` and the body; feedback calls use it.
- Not changed: API-6, API-7 accepted; API-8 false positive (`Bug_Backlog.md`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-client`: "Retry policy" (an unreadable success body is not retried); new "Request
  failures" (every failed API call reports a status and a code).

## Impact

- `apps/frontend/src/api/client.ts`, `src/app/queryClient.ts` (`isRetryable`),
  `src/features/feedback/api.ts`, tests.
- No backend change, no API change (OpenAPI `1.0.0`), no ranking change.
