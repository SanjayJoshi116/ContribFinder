## 1. Query client factory: retry policy and ended sessions (D1, H-5, F-7)

- [x] 1.1 New `src/app/queryClient.ts`:
  - `createQueryClient({ onUnauthenticated, retryDelay? })`;
  - `isRetryable(error)`: a non-`ApiError`, or an `ApiError` with status 0 or ≥ 500;
  - `queries.retry: count < 2 && isRetryable`, `mutations.retry: false`;
  - `QueryCache` and `MutationCache` `onError` call `onUnauthenticated` on a 401, except for
    `meQueryKey`, once until the next successful `/auth/me`;
  - default `staleTime` of 5 minutes for derived data; the status queries set 0.
- [x] 1.2 `main.tsx`: build the client with the factory. `onUnauthenticated` calls
  `endSession`, which removes `/auth/me` and navigates to `/?auth_error=session_ended`. The
  landing page clears the rest (`clearSignedInData`) on mount.
- [x] 1.3 `authErrors.ts`: add `session_ended` with "Your session ended. Sign in again to pick
  up where you left off." The landing page shows it through the existing banner.
- [x] 1.4 `test/render.tsx`: use `createQueryClient` with `retryDelay: 0` and the same 401
  handler bound to the memory router. Fix tests that assumed no retries on 5xx by giving them
  explicit handlers.
- [x] 1.5 Tests:
  - `404 not_analyzed` on `/profile` makes exactly one request and shows the
    profile-being-prepared message;
  - a 503 then 200 shows the data;
  - a 429 is requested once;
  - a 401 on a dashboard query lands on `/` with the session-ended notice and an empty cache;
  - a 401 on Save does the same;
  - a signed-out visit to `/` shows no notice.

## 2. Refresh on job transitions (D2, F-1, F-9)

- [x] 2.1 New `src/app/jobTransitions.ts`: `fetchStatusAndRefresh(queryClient, key, fetch,
  jobOf, refresh)`. It reads the cached previous status, fetches, and runs `refresh` when
  there was a previous status, the `id:status` key changed and the new job is inactive.
- [x] 2.2 `useSyncStatus` uses it, with `refresh` invalidating `['profile']`. Remove the
  unconditional invalidation.
- [x] 2.3 `useRecommendationStatus` uses it, with `refresh` invalidating
  `recommendationListKey`. Remove the `useEffect` and ref, and update the docstring.
- [x] 2.4 `useDiscoveryStatus` uses it, with `refresh` invalidating `recommendationStatusKey`.
  Remove the effect from `usePipelineStage`.
- [x] 2.5 Tests (count fetches through `mockFetch`):
  - remounting the dashboard with a COMPLETED sync refetches only the status;
  - RUNNING → COMPLETED refetches profile data once;
  - a new COMPLETED generation id refetches the list once with the list and the pipeline
    indicator both mounted;
  - a finished discovery fetches the recommendation status once.

## 3. Recommendation list: page recovery and Undo (D3, D4, F-3, F-8)

- [x] 3.1 `RecommendationList`:
  - a 404 with `page > 1` replaces the URL without `page`;
  - an empty success with `page > 1` and `previous` replaces it with `page - 1`;
  - render the loading text while recovering.
- [x] 3.2 `DismissUndo`: close through `useEffectEvent(onClose)`, with the timer effect
  depending on `project` only.
- [x] 3.3 Tests:
  - `/app?page=5` answering 404 shows page 1 with no error and no `page` in the URL;
  - dismissing the only card on page 2 shows page 1 and keeps the Undo notice;
  - with fake timers, dismiss, change a filter at 6 s, and the notice closes at 10 s.

## 4. Detail pages: hash scroll and invalid ids (D5, D6, F-5, F-6)

- [x] 4.1 New `src/lib/useScrollToHash.ts`, `useScrollToHash(ready)`. Once per location key,
  it calls `scrollIntoView`, using `behavior: 'auto'` under `prefers-reduced-motion: reduce`,
  then `focus({ preventScroll: true })`.
- [x] 4.2 `RelevantIssues`: the heading gets `tabIndex={-1}`. `RecommendationDetailPage`
  calls `useScrollToHash(recommendation.isSuccess)`.
- [x] 4.3 `RecommendationDetailPage` and `IssueDetailPage` render the not-found block when the
  id is not a positive integer:
  - "This link doesn't point to a recommendation." / "...to an issue.";
  - plus "Back to your dashboard";
  - no request.
- [x] 4.4 Tests:
  - `/app/recommendations/abc`, `/0` and `/app/issues/x` show the not-found text and make no
    detail request;
  - `/app/recommendations/7#relevant-issues` focuses the heading after load, with
    `scrollIntoView` stubbed and called once;
  - under reduced motion, `behavior` is `'auto'`.

## 5. Saved and hidden lists (D7, F-2)

- [x] 5.1 `features/feedback/api.ts`: `useSaved` and `useDismissed` become
  `useInfiniteQuery` over `?page=N&page_size=50` with `getNextPageParam` from `next`. Keys
  are unchanged.
- [x] 5.2 `SavedPage`:
  - flatten the pages;
  - an outline "Show more" button under each list while `hasNextPage`, disabled during
    `isFetchingNextPage`;
  - keep the empty and error states.
- [x] 5.3 Update `SYNCED_USER` and feedback test handlers to the new paths.
- [x] 5.4 Tests:
  - 2 pages of saved entries: "Show more" loads the second, then disappears;
  - restoring a hidden entry after loading 2 pages keeps the others listed.

## 6. Language chart from bytes (D8, H-17)

- [x] 6.1 `languageRows`: total from `bytes`; each `share`, `Other` included, is
  `bytes / total`.
- [x] 6.2 `LanguageChart` `percent`: `<1%` for `0 < share < 0.005`.
- [x] 6.3 Tests (`profile.test.tsx` or a `languages` unit test):
  - 8 languages plus 12 at 0.3% give `Other` 4%;
  - a top language at 0.2% shows `<1%`;
  - shares sum to 1 within rounding.

## 7. End-to-end settings and seed (D9, H-18)

- [x] 7.1 `config/settings/e2e.py`:
  - inherits `base`;
  - database name `contribfinder_e2e`;
  - locmem cache, `CELERY_TASK_ALWAYS_EAGER = True`, broker `memory://`, result backend
    `cache+memory://`;
  - GitHub API and OAuth base URLs at `http://127.0.0.1:9`;
  - test GitHub client id/secret, `FRONTEND_URL` and redirect URI for port 5174;
  - `INSTALLED_APPS += ["e2e"]`.
- [x] 7.2 New app `apps/backend/e2e/` with the management command `e2e_seed --out <path>`.
  It:
  - flushes;
  - seeds the active scoring config if absent;
  - creates `e2e-dashboard` and `e2e-delete` (synced: own repositories via
    `tests/profile_data`, ≥ 25 recommendable candidates with issues via
    `tests/repo_fixtures`, then `ProfileAnalysisService` and `RecommendationService` inline);
  - creates `e2e-unsynced` (account only);
  - writes a session per user and `{username: sessionid}` JSON.
- [x] 7.3 Backend tests:
  - `e2e_seed` is not a known command under `config.settings.test`;
  - the `e2e` app is absent from production and development `INSTALLED_APPS`;
  - a seed run under e2e settings, in a test that overrides `INSTALLED_APPS`, creates the
    users, at least 21 recommendations for `e2e-dashboard`, and sessions that authenticate
    `GET /api/v1/auth/me`.
- [x] 7.4 Ruff, mypy (strict) and format pass for the new modules.

## 8. Playwright suite (D9, H-18)

- [x] 8.1 `apps/frontend`:
  - add `@playwright/test` (exact version) to devDependencies and an `e2e` script;
  - add `playwright.config.ts`: Chromium, plus `webServer` entries for
    `scripts/e2e-backend.mjs` (`e2e_seed`, which creates, migrates and seeds, then Django on
    `127.0.0.1:8001`, through `scripts/uv.mjs` and `scripts/child.mjs`) and for Vite on
    `5174` with `VITE_API_PROXY_TARGET`;
  - Vitest excludes `e2e/`; ESLint and `tsconfig.node.json` include it;
  - gitignore `test-results/`, `playwright-report/` and the session file.
- [x] 8.2 `e2e/fixtures.ts`: a `signInAs(username)` fixture that adds the seeded `sessionid`
  cookie (path in `e2e/sessions.ts`).
- [x] 8.3 Specs:
  - `auth.spec.ts`: the sign-in start answers 302 to the GitHub authorize URL with `state`;
    `e2e-unsynced` at `/app` lands on onboarding; a cleared cookie plus in-app navigation shows
    the session-ended notice;
  - `dashboard.spec.ts`: `e2e-dashboard` sees summary, skills and recommendation cards with
    labels and no percentages; Save, then the card shows Saved and the project is on
    `/app/saved`; Dismiss, then Undo, then the project is back and not hidden; the "N relevant
    issues" link puts the Relevant issues heading in the viewport with focus;
  - `data.spec.ts`: `e2e-delete` deletes GitHub data from the dashboard and lands on
    onboarding.
- [x] 8.4 Run `npm run e2e` locally on Windows and confirm no `python` or `node` process from
  the suite is left afterwards.
- [x] 8.5 `.github/workflows/ci.yml`: new `e2e` job:
  - PostgreSQL service with `DATABASE_URL`;
  - `uv sync --frozen`, `npm ci`, `npx playwright install --with-deps chromium`,
    `npm run e2e`;
  - upload `playwright-report/` on failure.

## 9. Verification and housekeeping

- [x] 9.1 Frontend `npm run lint`, `format:check`, `typecheck`, `test` and `build` pass.
  Backend `ruff`, `mypy` and `pytest` pass. `npm run api:sync` shows no drift.
- [x] 9.2 Manual check in the running app (`npm start`) (2026-10-21: run as Playwright checks
  against the seeded e2e stack; the last two are covered by the e2e suite):
  - focus the window on the dashboard: only the status refetches (Network tab);
  - a 404 detail shows at once;
  - `?page=99` recovers;
  - "N relevant issues" scrolls to the issues;
  - a deleted session cookie returns to sign-in with the notice.
- [x] 9.3 `Bug_Backlog.md`: mark F-1, F-2, F-3, F-5, F-6, F-7, F-8, F-9, H-5, H-17 and H-18
  `fixed (frontend-correctness)`, update the shipped line (batch 9) and name the next batch.
- [x] 9.4 README: an "End-to-end tests" section (one-time Playwright browser install, the
  `contribfinder_e2e` database, `npm run e2e`).
- [x] 9.5 Release housekeeping (CLAUDE.md §8), patch release 0.12.8:
  - `VERSION`, the package files and lockfiles;
  - `CHANGELOG.md`, `features.txt`;
  - the README status;
  - CLAUDE.md §4 layout (`apps/backend/e2e/`, `apps/frontend/e2e/`) and the §7 entry.
