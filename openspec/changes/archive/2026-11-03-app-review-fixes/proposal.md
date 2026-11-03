## Why

The full review sweep of `apps/frontend/src/app/` (batch 44 of `Bug_Backlog.md`, APP-1…APP-10)
found that the job-transition refresh treats a vanished job as finished, can refresh twice when a
status fetch is cancelled, keeps running after sign-out, and that a just-started sync can be
overwritten by an older status answer so its finish is never seen. The session handling also
loses a 401 that arrives while a sign-out is pending. These are the last medium-priority frontend
findings before the low-priority modules.

## What Changes

- **APP-1**: a status whose job is `null` (deleted data) is never a newly finished job; no refresh.
- **APP-2, APP-3**: status queries pass the query's `AbortSignal` to the fetch; an aborted fetch
  never compares or refreshes, so a cancelled-and-restarted status fetch refreshes once and a
  sign-out's `cancelQueries` stops status requests.
- **APP-4**: starting a sync cancels an in-flight sync status fetch before writing the new PENDING
  job, so an older answer cannot replace it and stop polling.
- **APP-5**: a 401 swallowed while a sign-out mutation is pending is reported when that mutation
  fails (the session-ended path runs); a successful sign-out still ignores it.
- **APP-6**: if leaving for the sign-in page fails, the client resets its signed-out flag so later
  401s are reported again.
- **APP-9**: a test fails when a `['profile', ...]` query key in the source is not covered by an
  area of `AREA_KEYS`.
- **APP-10**: the data versions refresh invalidates every changed key in one `invalidateQueries`
  call (predicate) instead of one call per key.
- Accepted, no change: **APP-7** (by design since 0.12.8: the landing page clears the cache after
  the navigation commits; same user's data, memory only) and **APP-8** (the user's own list
  actions move the `recommendations` version, so the next route change refetches that area once
  more in the acting tab; the time is meant for other tabs and devices, and suppressing it would
  need a "seen" path that could also hide a concurrent background change).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-client`: "Refresh derived data on job transitions" (a vanished job is not finished; a
  cancelled status fetch triggers nothing; a started job is not replaced by an older status) and
  "Ended session returns to sign-in" (a 401 during a sign-out that then fails ends the session).

## Impact

- `apps/frontend/src/app/jobTransitions.ts`, `queryClient.ts`, `dataVersions.ts` and their tests.
- Status hooks: `features/sync/api.ts`, `features/discovery/api.ts`,
  `features/recommendations/api.ts` (signal); `useStartSync` (cancel before write).
- No backend, API or OpenAPI change; no ranking change. E2E not required (no browser flow
  changes), unit tests cover each fix.
