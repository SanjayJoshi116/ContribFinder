## Context

See proposal.md (Why) and `Bug_Backlog.md` batch 34. `createQueryClient` (`src/app/queryClient.ts`)
runs `endSession` (cancel, remove `['auth', 'me']`, navigate to `SESSION_ENDED_PATH`) on the
first 401 of any query except `/auth/me`, and ignores 401s while a mutation marked
`endsSession` is pending (`signedOut`). `clearSignedInData` drops every query but the identity,
plus the mutation cache; the landing page calls it for `session_ended`. `DataSection` and
`DisconnectSection` both render in `AppShell`, which redirects to `/onboarding` when the sync
status has no `last_synced_at`. TanStack Query v5 keeps `data` when a refetch fails (status
`error`), skips per-call `mutate` callbacks after unmount, and runs hook-level callbacks always.
Project rule: never remove a query a mounted page observes (data-versions-fixes).

## Goals / Non-Goals

**Goals:** close AUTH-1…AUTH-9, each with a test, without a backend or API change.

**Non-Goals:** reworking the session model, adding a sign-out confirmation, or changing what the
backend deletes.

## Decisions

**D1 — Own keys only.** `authErrorMessage` returns `MESSAGES[code]` only when
`Object.hasOwn(MESSAGES, code)`, else `MESSAGES.failed` (AUTH-1).

**D2 — Identity refresh.** `RequireAuth` renders the `Outlet` whenever `me.data` exists; the
loading and error screens and the 401 redirect apply only without data (AUTH-2). The query cache
`onError` treats a 401 on `/auth/me` as an ended session when the query held data
(`query.state.data !== undefined`), so a signed-in user goes through `endSession`; a first visit
(no data) stays silent (AUTH-3).

**D3 — One way out.** `leaveSignedIn(queryClient, navigate, path)` in `queryClient.ts`:
`await cancelQueries()`, remove the identity, `await navigate(path)` (the signed-in pages
unmount), then `clearSignedInData`. `useLogout`, `useDisconnectGitHub` and `useDeleteAccount`
call it from their hook-level `onSuccess` with `useNavigate()` and path `/`; the components
call `mutate()` without callbacks (AUTH-4, AUTH-5, AUTH-7).

**D4 — Delete GitHub data.** Hook-level `onSuccess`: cancel `['profile']` and `['jobs']`, await
the identity and `['sync']` refetch (the dashboard redirects to `/onboarding`),
`navigate('/onboarding')` from the hook, then remove `['profile']` and `['jobs']` (no page
observes them now) and reset the versions as before (AUTH-6, AUTH-7).

**D5 — One account action at a time.** `accountMutationKey = ['account']` prefixes the four
mutations' keys; both sections disable their buttons while `useIsMutating({ mutationKey:
accountMutationKey }) > 0`. With actions serialized, the single `signedOut` flag holds
(AUTH-8).

**D6 — Test data.** The disconnect test answers `{ revocation: 'queued' }` (AUTH-9).

## Risks / Trade-offs

- [A refetch error with data is no longer shown] → the next successful refetch or any 401 still
  decides; a lasting failure surfaces in the page's own queries.
- [`clearSignedInData` after navigating also drops the finished mutation] → nothing reads it
  once the signed-in pages are gone.
- [Delete GitHub data still waits on the sync status refetch before leaving] → same wait as
  today; the hook navigates even if the redirect did not happen.
