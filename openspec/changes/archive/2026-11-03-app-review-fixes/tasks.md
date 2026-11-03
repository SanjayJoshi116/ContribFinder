## 1. Job transitions

- [x] 1.1 APP-2, APP-3: `fetchStatusAndRefresh(queryClient, key, signal, fetchStatus, refresh)`
  with `fetchStatus: (signal) => Promise<S>`; return before comparing when `signal.aborted`.
  Sync, discovery and generation status hooks pass the `queryFn` signal to `apiFetch` (D1).
  - Test: a status fetch cancelled by `invalidateQueries` and restarted, both returning a newly
    finished job, runs the refresh once.
  - Test: `cancelQueries` aborts an in-flight status request (the fetch sees an aborted signal)
    and no refresh runs.
- [x] 1.2 APP-1: no refresh when `status.job` is null (D2).
  - Test: previous COMPLETED job, then `{ job: null }` → refresh not called.
  - Delete-data path: covered by the unit test above (`jobTransitions.test.ts`); an
    integration count was not added, since delete-data's own `resetQueries` refetches the
    versions anyway and `['jobs']` is cancelled and removed, so the counts cannot tell the two
    apart.
- [x] 1.3 APP-4: `useStartSync.onSuccess` awaits `cancelQueries({ queryKey: syncStatusKey })`
  before `setQueryData` (D3).
  - Test: a `/sync/status` answer with the old finished job held until after the start resolves
    leaves the PENDING job shown and polling on.

## 2. Session

- [x] 2.1 APP-5: remember a 401 swallowed while a sign-out mutation is pending; on that
  mutation's error end the session (D4).
  - Test: logout pending, a query answers 401, logout fails with a network error → sign-in page
    with the session-ended notice.
  - Test: same, logout succeeds → no notice (unchanged).
- [x] 2.2 APP-6: `unauthenticated` resets `signedOut` when `endSession` rejects (D5).
  - Test: a `navigate` that rejects once, then a second 401 → `navigate` called again.

## 3. Data versions

- [x] 3.1 APP-10: one `invalidateQueries` with a `partialMatchKey` predicate over the changed
  areas' keys; nothing when no area changed (D7).
  - Existing data-versions tests pass unchanged (same queries refetched once).
- [x] 3.2 APP-9: source-scan test (D6): every `['profile', '<name>'` literal outside tests is
  covered by `AREA_KEYS`; the scan finds at least the nine listed names.

## 4. Backlog

- [x] 4.1 `Bug_Backlog.md` batch 44: APP-1…APP-6, APP-9, APP-10 fixed (0.12.55); APP-7, APP-8
  accepted (reasons as in the proposal); sweep table and open items updated.

## 5. Checks

- [x] 5.1 Frontend (`apps/frontend`): `npm test`, `npm run lint`, `npm run typecheck`,
  `npm run format:check`, `npm run build`. No API change (`api:sync` not needed); no e2e (no
  browser flow changes).
- [x] 5.2 `openspec validate app-review-fixes`.

## 6. Release

- [x] 6.1 `/simplify`, then `/code-review` on the fix diff; record and fix (or the owner skips
  this step) — skipped by the owner (2026-11-03).
- [x] 6.2 Archive (syncs the `web-client` delta); release housekeeping (CLAUDE.md §8, 0.12.55);
  commit only when the owner says so.
