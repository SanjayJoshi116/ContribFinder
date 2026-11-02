## Why

The review sweep's ninth module, `apps/frontend/src/features/auth/` (`Bug_Backlog.md` batch 34,
AUTH-1…AUTH-9), found that a link with `?auth_error=__proto__` breaks the sign-in page, that a
failed background refresh of the identity replaces every signed-in page with an error, that a
401 on that refresh skips the ended-session flow, and that the ways out of the signed-in app
(log out, disconnect, delete data, delete account) leave user data cached, remove queries that
pages still observe, rely on navigation callbacks that never run, and can overlap. The security
review of the module found nothing.

## What Changes

- AUTH-1: `authErrorMessage` reads only its own message keys; anything else is the generic
  failure message.
- AUTH-2: `RequireAuth` keeps the signed-in pages while it has an identity; the error page shows
  only when none was ever loaded.
- AUTH-3: a 401 on `/auth/me` after it had succeeded ends the session like any other 401
  (notice, cache cleared).
- AUTH-4, AUTH-5, AUTH-7: log out, disconnect and delete account leave through one helper
  (`leaveSignedIn`): cancel, drop the identity, navigate, then drop every other cached query
  and mutation. Navigation lives in the hooks, not in per-call callbacks.
- AUTH-6, AUTH-7: delete GitHub data refetches the sync status (the dashboard redirects to
  onboarding), navigates from the hook, then removes the profile and job queries.
- AUTH-8: every account action shares one mutation key; both sections disable their buttons
  while any of them is pending.
- AUTH-9: the disconnect test mocks `revocation: 'queued'`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-client`: "Ended session returns to sign-in" (the identity refresh counts; a failed
  refresh that is not 401 keeps the pages); new "Leaving the signed-in app" (no cached user data
  after log out, disconnect or account deletion; one account action at a time; unknown sign-in
  error codes show the generic message).

## Impact

- `apps/frontend/src/features/auth/{api.ts,authErrors.ts,RequireAuth.tsx,DataSection.tsx,
  DisconnectSection.tsx,auth.test.tsx}`, `src/app/queryClient.ts`; possibly the e2e data spec.
- No backend change, no API change (OpenAPI `1.0.0`), no ranking change.
