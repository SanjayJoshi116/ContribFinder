## Context

See proposal.md (Why) and `Bug_Backlog.md` batch 33. `apiFetch` (`client.ts`) is the only path to
the backend. `createQueryClient` (`src/app/queryClient.ts`) retries data queries when
`isRetryable(error)`: today any non-`ApiError`, status 0 or 5xx. Mutations never retry. The CSRF
cookie is set by `login()` (token rotation) and by `GET /auth/csrf/` (`CsrfView`, anon
throttled); `CSRF_USE_SESSIONS` is off (double-submit).

## Goals / Non-Goals

**Goals:** close API-1…API-5 and API-9, each with a test, without a backend or API change.

**Non-Goals:** HTTP-date `Retry-After` (API-7), non-204 empty successes (API-6), retry on
`csrf_failed` (API-8, false positive); changing which statuses are retried.

## Decisions

**D1 — One error type.** `apiFetch` wraps `fetch` rejections (not `AbortError`, which TanStack
Query needs to see as cancellation) in `ApiError(0, 'network_error', ...)`, and a 2xx body that
fails `response.json()` in `ApiError(response.status, 'invalid_response', ...)`. `isRetryable`
becomes `error instanceof ApiError && (error.status === 0 || error.status >= 500)`, so a
`SyntaxError` or a bug in a `queryFn` is no longer retried. An `invalid_response` keeps its 2xx
status, so it is not retried (API-1).

**D2 — Fallback keeps the wait.** The non-envelope `ApiError` passes `retryAfter` (API-2).

**D3 — CSRF prelude.** One module-level `pending: Promise<string> | null`, cleared when it
settles (API-4). A non-ok `/auth/csrf/` response throws `toApiError(response)`; a rejected fetch
is `network_error`; `csrf_unavailable` stays only for an ok response that set no cookie (API-3).
`ensureCsrfToken({ keepalive })` passes `keepalive` to the prelude; `apiFetch` forwards
`init.keepalive` (API-5). A keepalive prelude joins a pending one rather than starting another.

**D4 — JSON bodies.** `apiFetch<T>(path, init: ApiInit = {})` where `ApiInit = RequestInit & {
json?: unknown }`: with `json`, the body is `JSON.stringify(json)` and `Content-Type:
application/json` is set (`body` alongside `json` is a type error). `recordFeedback` and
`useDismiss` use it (API-9).

## Risks / Trade-offs

- [Queries whose `queryFn` throws a non-`ApiError` stop retrying] → only bugs or bad bodies;
  network failures become `ApiError(0)` and still retry.
- [`AbortError` passed through unwrapped] → TanStack Query's cancellation relies on it.
- [A keepalive prelude joining a non-keepalive pending one] → the window is one request; the
  event is fire-and-forget by design.
