## 1. Client

- [x] 1.1 API-1: `apiFetch` wraps fetch rejections (except `AbortError`) as `ApiError(0, 'network_error')` and an unreadable 2xx body as `ApiError(status, 'invalid_response')` (D1); tests: offline, HTML 200, abort passes through
- [x] 1.2 API-1: `isRetryable` retries only `ApiError` with status 0 or 5xx (D1); tests: `invalid_response` and a thrown `SyntaxError` not retried, `network_error` retried twice
- [x] 1.3 API-2: non-envelope errors keep `retryAfter` (D2); test: 503 plain text with `Retry-After: 30`
- [x] 1.4 API-3, API-4, API-5: CSRF prelude shares one pending promise, raises the token request's own error, forwards `keepalive` (D3); tests: 429 envelope, two concurrent mutations send one prelude, keepalive prelude
- [x] 1.5 API-9: `json` init option; `recordFeedback` and `useDismiss` use it (D4); test: body and `Content-Type` set

## 2. Checks

- [x] 2.1 Frontend `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run build`; `npm run e2e` (the feedback flow uses the client)

## 3. Release (workflow steps 6-8)

- [x] 3.1 `/simplify`, then `/code-review` on the fix diff; record and fix (deferred by the owner, 2026-11-02: run later)
- [x] 3.2 Archive (delta into `web-client`); `Bug_Backlog.md` batch 33 rows marked fixed
- [x] 3.3 Release housekeeping (CLAUDE.md §8); commit only when the owner says so
