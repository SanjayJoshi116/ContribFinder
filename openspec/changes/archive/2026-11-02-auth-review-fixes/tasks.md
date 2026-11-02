## 1. Sign-in page and route guard

- [x] 1.1 AUTH-1: `authErrorMessage` uses `Object.hasOwn` (D1); test: `__proto__`, `constructor` show the generic message
- [x] 1.2 AUTH-2, AUTH-3: `RequireAuth` keeps the `Outlet` while `me.data` exists; the query cache ends the session on a 401 from `/auth/me` that held data (D2); tests: refetch 503 keeps the page, refetch 401 shows the session-ended notice, first visit 401 shows none

## 2. Leaving the signed-in app

- [x] 2.1 AUTH-4, AUTH-5, AUTH-7: `leaveSignedIn` in `queryClient.ts`; log out, disconnect and delete account call it from the hooks; components call `mutate()` without callbacks (D3); tests: after log out and account deletion no `['profile']` or `['jobs']` query remains, the landing page shows no notice
- [x] 2.2 AUTH-6, AUTH-7: delete GitHub data navigates from the hook and removes the profile and job queries after leaving the dashboard (D4); test: lands on `/onboarding`
- [x] 2.3 AUTH-8: `accountMutationKey`; both sections disabled while an account action is pending (D5); test: Disconnect disabled while Delete account is pending
- [x] 2.4 AUTH-9: disconnect test mocks `revocation: 'queued'` (D6)

## 3. Checks

- [x] 3.1 Frontend `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run build`; `npm run e2e` (sign-out and delete-data flows)

## 4. Release (workflow steps 6-8)

- [x] 4.1 `/simplify`, then `/code-review` on the fix diff; record and fix (deferred by the owner, 2026-11-02: run later)
- [x] 4.2 Archive (delta into `web-client`); `Bug_Backlog.md` batch 34 rows marked fixed
- [x] 4.3 Release housekeeping (CLAUDE.md §8); commit only when the owner says so
