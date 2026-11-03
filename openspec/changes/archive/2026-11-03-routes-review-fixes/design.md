## Context

Findings and verdicts: `Bug_Backlog.md` batch 45 (ROUTE-1…ROUTE-10); motivation in
`proposal.md`; behavior in the `web-client` delta. Route tree (`routes/routes.tsx`):
`RequireAuth` → `SignedInLayout` → `AppShell`, detail pages, saved, onboarding. TanStack Query 5:
`isError`/`isSuccess` describe the last fetch, while `data` survives a failed refetch.

## Goals / Non-Goals

**Goals:**
- Gate every page branch on `data` first, the way `RequireAuth` already does with `me.data`.
- One message helper for sync start errors.

**Non-Goals:**
- A not-found page for `*` (ROUTE-10's second half; a UX decision for the interface revamp,
  `ideas.md` §18).
- Detail pages under `features/` (FI-3 is batch 46).

## Decisions

**D1. Previous route, not first location (ROUTE-1, ROUTE-7).** `SignedInLayout` keeps
`useRef(pathname + search + hash)`; the effect refetches the versions when the current
`pathname + search + hash` differs from the ref, then stores it. Back to the first page differs from the
detail page before it, so it refetches; a state-only `replace` keeps the same string. The mount is
covered by the query's own mount fetch (the ref starts at the first route). Alternative: a
"mounted" boolean keyed on `location.key`; rejected, it still fires on state-only navigations.

**D2. Data before error (ROUTE-2, ROUTE-3).** `AppShell` and `OnboardingPage`: `isPending` →
loading; no `data` → error page; otherwise render from `data`. `AppShell`'s `analyzed` becomes
`developer.data !== undefined`; the "being prepared" / "could not load" branch runs only without
data, so `useSkills`/`useInterests` stay enabled across a failed refetch. A `not_analyzed` 404 on
a refetch with data cached keeps the shown profile (deletion removes `['profile']` itself).

**D3. Error line for a failed first load (ROUTE-4).** Skills, interests and repositories: pending
→ "Loading…"; `isError` with no data → `role="alert"` "Could not load your …. Please refresh the
page."; otherwise the list. Texts live next to the other dashboard texts in `AppShell`.

**D4. `startErrorText(error, at)` (ROUTE-5, ROUTE-6)** in `features/sync/messages.ts`:
`sync_cooldown` with `retryAfter` → "Your data was synced recently. You can refresh again after
{time}." where time = `at + retryAfter` formatted `timeStyle: 'short'` (date added when it is not
today); otherwise `error.message`. `at` is the mutation's `submittedAt` (TanStack mutation state),
close to the arrival of the 429. Both pages render it. `formatWait` is removed if nothing else
uses it. Alternative: reset the mutation after `retryAfter` with a timer; rejected, a timer per
page for a rare message, and the clock time is clearer.

**D5. Identity through the outlet (ROUTE-8).** `RequireAuth` renders `<Outlet context={me.data} />`;
`useSignedInUser()` in `features/auth/api.ts` returns `useOutletContext<Me>()`; `SignedInLayout`
reads it and passes it on (`<Outlet context={me} />`), so `AppShell` reads it too. The type is
guaranteed by construction; the `!!me` / `me &&` / `if (!me) return null` branches go.
`useDataVersions(enabled)` keeps its parameter (other callers may pass false), the layout passes
nothing. Alternative: a hook that throws when `useMe().data` is missing; rejected, it can run in
the render where `endSession` has just removed the identity.

**D6. One redirect on onboarding (ROUTE-9).** Remove the effect; the render-time `<Navigate>`
covers COMPLETED (its status answer carries `last_synced_at`).

**D7. Nothing while the identity loads (ROUTE-10).** `LandingPage` returns `null` while
`me.isPending`; 401 or another error shows the page as now. The `?auth_error=` cache clearing
effect still runs (it does not depend on the render branch).

## Risks / Trade-offs

- [A stale profile stays shown while its refetch keeps failing] → Intended (spec "Failed refresh
  keeps the page"); the next successful fetch replaces it, and a 401 ends the session.
- [Blank landing while `/auth/me` is slow] → Same moment as `RequireAuth`'s "Loading…"; the
  request is one small read. A spinner can come with the interface revamp.
- [`submittedAt` vs arrival time] → Off by the request's latency (milliseconds to seconds); the
  message names a minute.
