## Why

The full review sweep of `apps/frontend/src/routes/` (batch 45 of `Bug_Backlog.md`,
ROUTE-1…ROUTE-10) found that one failed background refetch replaces the whole dashboard, the
developer profile or onboarding with an error page, that failed loads of skills, interests and
repositories look like empty results (CLAUDE.md §3: failures are never shown as empty data), and
that Back to the first page never refreshes the data versions. Smaller rows: the cooldown text is
missing on onboarding and goes stale on the dashboard, duplicate navigations, dead code, and a
signed-in user briefly sees the sign-in page.

## What Changes

- **ROUTE-1, ROUTE-7**: the signed-in layout refetches the data versions whenever the path,
  query or fragment differs from the previous route (Back to the first page included); a state-only
  navigation is not a route change.
- **ROUTE-2**: the dashboard and onboarding show the "Could not load" error only when no sync
  status was ever loaded; a failed poll keeps the page.
- **ROUTE-3**: the dashboard keeps the developer profile (and skills, interests, languages) when a
  refetch fails; "being prepared" and the error show only without data.
- **ROUTE-4**: skills, interests and repositories show an error line when their load failed with
  no data, never an empty list.
- **ROUTE-5, ROUTE-6**: one sync-start error text for the dashboard and onboarding; the cooldown
  names the clock time when a refresh becomes possible ("after 14:05") instead of a countdown
  that goes stale.
- **ROUTE-8**: the signed-in identity reaches the layout and pages through the route outlet, so
  the impossible "no identity" branches go away.
- **ROUTE-9**: onboarding navigates to the dashboard once (the render-time redirect; the effect
  is removed).
- **ROUTE-10**: the sign-in page renders nothing while the identity is loading, so a signed-in
  user opening `/` or an unknown path does not see "Continue with GitHub". A not-found page stays
  out of scope (a separate UX choice).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-client`: "Refresh derived data by data versions" (what a route change is; Back included);
  new requirements "Failed refresh keeps the page", "Sync start errors" and "Sign-in page while
  the identity loads".

## Impact

- `apps/frontend/src/routes/` (`SignedInLayout`, `AppShell`, `OnboardingPage`, `LandingPage`),
  `features/auth/RequireAuth.tsx` and `features/auth/api.ts` (signed-in identity hook),
  `features/sync/messages.ts` (start error text), with tests.
- No backend, API or OpenAPI change; no ranking change. E2E: the sign-in and dashboard flows are
  touched only in loading/error branches; unit tests cover each fix, so no e2e run is required.
