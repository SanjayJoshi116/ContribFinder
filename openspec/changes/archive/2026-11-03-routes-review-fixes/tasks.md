## 1. Signed-in layout

- [x] 1.1 ROUTE-1, ROUTE-7: `SignedInLayout` refetches the versions when `pathname + search + hash`
  differs from the previous route (D1).
  - Test: dashboard → recommendation → Back: versions fetched on the way back.
  - Test: a state-only `replace` to the same path fetches nothing.
- [x] 1.2 ROUTE-8: `RequireAuth` passes the identity as outlet context; `useSignedInUser()`;
  `SignedInLayout` passes it on; `AppShell` uses it; dead `me` branches removed (D5).
  - Existing auth and layout tests pass.

## 2. Dashboard and onboarding

- [x] 2.1 ROUTE-2: `AppShell` and `OnboardingPage` show the error page only without
  `status.data` (D2).
  - Test: a sync status poll failing with 503 after retries keeps the dashboard.
- [x] 2.2 ROUTE-3: `analyzed` from `developer.data`; skills and interests stay enabled (D2).
  - Test: a developer profile refetch failing with 503 keeps summary and skills.
- [x] 2.3 ROUTE-4: error lines for skills, interests and repositories that failed with no data (D3).
  - Test: skills 503 on first load → "Could not load your skills" alert, no empty list.
- [x] 2.4 ROUTE-5, ROUTE-6: `startErrorText(error, at)` in `features/sync/messages.ts`, used by
  both pages; cooldown names the clock time (D4).
  - Test: dashboard cooldown with `Retry-After: 240` shows the time 4 minutes after the click.
  - Test: onboarding "Try again" with the same answer shows the same text.
  - Unit test: `startErrorText` for cooldown and for another error.
- [x] 2.5 ROUTE-9: remove the onboarding navigation effect (D6).
  - Existing "onboarding completes" test passes; one navigation to `/app`.

## 3. Sign-in page

- [x] 3.1 ROUTE-10: `LandingPage` renders nothing while `me.isPending` (D7).
  - Test: signed-in user at `/` never sees "Continue with GitHub" and lands on `/app`.
  - Existing signed-out and `auth_error` tests pass.

## 4. Backlog

- [x] 4.1 `Bug_Backlog.md` batch 45: ROUTE-1…ROUTE-10 fixed (0.12.56; ROUTE-10 without the
  not-found page); sweep text updated.

## 5. Checks

- [x] 5.1 Frontend (`apps/frontend`): `npm test`, `npm run lint`, `npm run typecheck`,
  `npm run format:check`, `npm run build`. No API change; e2e not required (D7 and error
  branches only), run it if a dashboard or sign-in spec is touched.
- [x] 5.2 `openspec validate routes-review-fixes --strict`.

## 6. Release

- [x] 6.1 `/simplify`, then `/code-review` on the fix diff; record and fix (or the owner skips
  this step) — skipped by the owner (2026-11-03).
- [x] 6.2 Archive (syncs the `web-client` delta); release housekeeping (CLAUDE.md §8, 0.12.56);
  commit only when the owner says so.
