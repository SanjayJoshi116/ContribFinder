## Context

Findings and verdicts: `Bug_Backlog.md` batch 44 (APP-1…APP-10); motivation in `proposal.md`.
`fetchStatusAndRefresh` (`src/app/jobTransitions.ts`) runs inside each status query's `queryFn`
(sync, discovery, generation): it reads the cached previous status, fetches, and starts the
refresh when the job key changed to a non-active job. `createQueryClient` (`src/app/queryClient.ts`)
holds one `signedOut` flag that turns 401s into `endSession` once. `useDataVersions` compares
versions in an effect and invalidates `AREA_KEYS` of changed areas. TanStack Query 5.104.

## Goals / Non-Goals

**Goals:**
- Keep the job-transition comparison in the `queryFn` (one reaction per fetch, however many
  observers) and make it safe against cancellation.
- Fix each confirmed row with the smallest change and one test per fix.

**Non-Goals:**
- APP-7, APP-8 (accepted, see proposal). No change to stale times, area membership or the
  invalidations of the user's own actions.
- No backend or API change.

## Decisions

**D1. Signal, not an effect (APP-2, APP-3).** `fetchStatusAndRefresh(queryClient, key, signal,
fetchStatus, refresh)` with `fetchStatus: (signal) => Promise<S>`; each status hook passes the
`queryFn`'s `signal` to `apiFetch(path, { signal })`. TanStack aborts a consumed signal when the
fetch is cancelled (`cancelRefetch`, `cancelQueries`), so the abandoned run rejects with
`AbortError` and never compares; after the await it also returns before comparing when
`signal.aborted` (an answer that resolved just before the abort). The restarted run reads the
same restored previous status and is the only one that refreshes. Alternative: move the
comparison into an effect, as `useDataVersions` (U-6). Rejected: status hooks are used by several
components (pipeline indicator, dashboard, onboarding), so the effect would need a single
designated observer for three statuses; the signal keeps "once per fetch" as it is.

**D2. A missing job is not a transition (APP-1).** The comparison also requires `status.job` to be
non-null. A job only becomes null when the user's data is deleted, and deletion handles its own
cache (`useDeleteGitHubData`).

**D3. Cancel before writing the started job (APP-4).** `useStartSync.onSuccess` awaits
`queryClient.cancelQueries({ queryKey: syncStatusKey })` before `setQueryData`. The cancelled
fetch restores the previous data and is then overwritten by the PENDING job; with D1 it starts no
refresh. Generation and restore invalidate their status instead of writing it, so they need
nothing (checked: `setQueryData` on a status key appears only in `useStartSync`).

**D4. A swallowed 401 is remembered (APP-5).** In `createQueryClient`, a 401 seen while a
sign-out mutation is pending sets `missed401`. The sign-out's `onMutate` clears it; on its error
the flag `signedOut` is reset and, if `missed401` was set (or the error itself is a 401), the
session ends through the usual path. A successful sign-out drops the flag. Account actions are
exclusive (`useAccountActionPending`), so one boolean is enough.

**D5. Failed navigation resets the flag (APP-6).** `unauthenticated` runs
`endSession(...).catch(() => { signedOut = false })`, so a later 401 tries again. No logging
beyond what the router does.

**D6. Area coverage test (APP-9).** A Vitest test reads every non-test source file under `src/`
through `import.meta.glob('/src/**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true })`,
collects the second element of each `['profile', '<name>'` literal, and asserts each name is the
second element of some `AREA_KEYS` key (plain `['profile']` prefixes, used by delete-data, are
skipped). Alternative: render each page and inspect the cache; rejected as slow and dependent on
which branches a page renders.

**D7. One invalidation (APP-10).** `queryClient.invalidateQueries({ predicate: (query) =>
keys.some((key) => partialMatchKey(query.queryKey, key)) })`, skipped when `keys` is empty.
`partialMatchKey` is exported by `@tanstack/react-query` (query-core). Refetch behavior is the same
as per-key calls (`refetchType: 'active'`).

## Risks / Trade-offs

- [`apiFetch` must forward `signal` and let `AbortError` through] → It does since 0.12.46
  (API-1: an `AbortError` passes through); a test asserts an aborted status fetch refreshes nothing.
- [Source-scan test misses a key built without a literal, e.g. a spread of a constant] → Keys are
  built from literal roots today (`ROOT = ['profile', 'recommendations']`); the test also checks
  that it found at least the nine listed names, so a refactor that hides literals fails loudly.
- [D4 ends the session after a failed logout the user meant anyway] → Intended: the session is
  already gone server-side; the notice is accurate.
