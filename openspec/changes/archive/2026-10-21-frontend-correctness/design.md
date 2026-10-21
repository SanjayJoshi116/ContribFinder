## Context

Server state in the SPA is TanStack Query v5. `main.tsx` builds a bare `new QueryClient()`, so
production uses the library defaults: 3 retries with backoff for every error, refetch on
window focus. Tests build their own client with `retry: false` (`test/render.tsx`), so they
never see the production policy (H-5).

Three status queries drive the derived data:
- `useSyncStatus` (`['sync', 'status']`);
- `useDiscoveryStatus`;
- `useRecommendationStatus` (`['profile', 'recommendations', 'status']`).

Today they work like this:
- `useSyncStatus` invalidates `['profile']` inside its `queryFn` whenever the job is
  COMPLETED. That is the steady state, so every focus or remount refetches the whole dashboard
  (F-1).
- `useRecommendationStatus` compares job keys in a `useEffect` with a per-component ref. Every
  observer runs it, including the passive one in `usePipelineStage`, so one finished generation
  invalidates the list twice (F-9).

Only `useMe` treats 401 specially. `RequireAuth` redirects when `/auth/me` fails, which happens
after up to 60 s of `staleTime`, on focus or on mount (F-7).

The backend already has everything the browser tests need, except a way to sign in without
GitHub:
- `REDIS_URL` empty runs Celery inline;
- generation reads only PostgreSQL;
- delete-data does not call GitHub.

`base.py` reads `.env`, so a developer's local `REDIS_URL` would leak into any settings module
that inherits it.

## Goals / Non-Goals

**Goals:**
- One query-client factory used by production and tests, holding the retry policy and the 401
  handling.
- Refresh on job transitions computed once per fetch, from the cached previous status, the
  same way for all three status queries.
- Browser tests that exercise the real API, sessions, CSRF and database, with no GitHub call
  and no sign-in path outside the end-to-end settings.

**Non-Goals:**
- Visual redesign. The interface keeps its current neutral token set (`index.css`) and shadcn
  components. New states reuse the existing patterns (`role="alert"` paragraph plus a link,
  outline `Button`).
- Changes to `refetchOnWindowFocus`. Status queries keep refetching on focus and mount;
  derived data no longer does, because of its stale time (D1).
- End-to-end coverage of the OAuth callback, sync, discovery or disconnect (all call GitHub).
- Firefox and WebKit. Chromium only in CI for now.

## Decisions

### D1. `createQueryClient()` in `src/app/queryClient.ts` (H-5, F-7)

A factory takes `{ onUnauthenticated, retryDelay? }` and returns a `QueryClient` with:
- `queries.retry: (count, error) => count < 2 && isRetryable(error)`. `isRetryable` is true for
  an `ApiError` with status 0 (CSRF fetch failure) or ≥ 500, and for a non-`ApiError` (a `fetch`
  `TypeError`: network failure).
- `mutations.retry: false`.
- A `QueryCache` and a `MutationCache`, each with `onError` that calls `onUnauthenticated` for
  `ApiError.status === 401`, except when the failing query is `meQueryKey`. A 401 on `/auth/me`
  is the normal signed-out answer: the landing page and `RequireAuth` already handle it, and it
  must not show the notice to a first-time visitor.

- `queries.staleTime: DERIVED_STALE_TIME_MS` (5 minutes). With TanStack's default of 0, a
  remount refetches every query even when nothing invalidated it, so F-1 can't be fixed by
  invalidation alone. Derived data changes only when a job finishes (D2 refreshes it) or
  through the user's own mutations (which invalidate it). The three status queries set
  `staleTime: 0`, so they still refetch on mount and focus. A finished generation also
  invalidates recommendation details, issue details and the saved list, which show the
  current recommendation.

`main.tsx` and `test/render.tsx` pass the same handler:

```ts
onUnauthenticated: () =>
  void endSession(queryClient, (path) => router.navigate(path, { replace: true }))
```

`endSession` cancels queries, removes only the `/auth/me` entry, so the sign-in page asks the
server again instead of redirecting back to `/app`, and navigates to
`/?auth_error=session_ended`. The landing page then calls `clearSignedInData` (every query but
`/auth/me`, plus mutations) in a mount effect for that code.

Clearing inside `endSession` doesn't work. The navigation promise resolves before React
unmounts the dashboard, so its observers refetch whatever was just removed. The landing page's
effect runs after that commit.

The handler runs once per burst: a flag in the factory stays set until the next successful
`/auth/me`, because the dashboard's parallel queries all fail together. `useMe` keeps its own `retry` (401 never
retried), which matches the new default.

`test/render.tsx` uses the factory with `retryDelay: 0` and the same `onUnauthenticated` wired
to the memory router. Tests then see real retry counts. Existing tests that relied on no
retries for 5xx get explicit handlers.

The notice is a new entry in `authErrors.ts` and shows through the existing `auth_error`
banner on the landing page. Copy: "Your session ended. Sign in again to pick up where you left
off." It is a plain statement of what happened plus the action, in the voice of the other
`auth_error` messages, without an apology.

Alternatives rejected:
- A `useEffect` in `RequireAuth` watching all queries: it still waits for a render, and misses
  mutations.
- Retrying 429 after `Retry-After`: the backend's throttles are per minute, so a retry inside a
  query would mostly fail again. The UI already shows the wait for the sync cooldown.

### D2. Transition refresh inside the status `queryFn` (F-1, F-9)

A helper in `src/app/jobTransitions.ts`:

```ts
async function fetchStatusAndRefresh<S>(queryClient, key, fetch: () => Promise<S>,
  jobOf: (s: S) => SyncJob | null | undefined, refresh: () => Promise<unknown>): Promise<S>
```

It reads the previous status with `queryClient.getQueryData(key)` before fetching. After the
fetch, it calls `refresh()` when:
- there was a previous status;
- the job key (`id:status`) changed;
- the new job is no longer active.

Then it returns the status.

All three status queries use it:
- sync refreshes `['profile']`;
- recommendations refresh `recommendationListKey`;
- discovery keeps its "look for the generation" step (today in `usePipelineStage`) as its
  `refresh`.

Because it runs in the `queryFn`, TanStack's de-duplication gives one run per fetch, whatever
the number of observers. The `useEffect` and ref in `useRecommendationStatus`, and the one in
`usePipelineStage`, go away.

With no previous status (first load, or after `clear()`), there is nothing stale to refresh: the
derived queries fetch for the first time anyway. A job that started and finished between two
polls has a new id, so it still refreshes.

Alternatives rejected:
- `useEffect` in one designated observer: fragile. Whichever component mounts first owns it,
  and F-9 is exactly this bug.
- Query `select` or `structuralSharing` callbacks: they run per observer too.

### D3. List page recovery in `RecommendationList` (F-3)

A `useEffect` keyed on the list result:
- An `ApiError` 404 with `page > 1` → `update('page', '')` (page 1). DRF's "Invalid page" 404
  carries no last-page number, so a second request would be needed to find it. With filters
  applied, the unfiltered status count can't tell us either, and page 1 is always valid.
- A success with 0 results, `page > 1` and `previous` set → `update('page', String(page - 1))`.

Both replace the URL. The dismiss `Undo` state lives in component state, so it survives the
change. While the effect is pending, the list renders the loading text, not the error or the
empty state, so no wrong message flashes.

### D4. Undo window measured from the dismissal (F-8)

`DismissUndo` closes through `useEffectEvent(onClose)` (React 19.2), and its timer effect
depends on `project` only. `closeUndo` in `RecommendationList` no longer needs to be stable, so
it reads `location` freely.

Alternative rejected: a ref holding the latest `onClose`. It is the same thing done by hand,
and the hooks lint rule understands `useEffectEvent`.

### D5. Hash scroll after load (F-5)

`useScrollToHash(ready: boolean)` in `src/lib/useScrollToHash.ts`. When `ready` turns true and
`location.hash` names an element, it:
- calls `scrollIntoView({ block: 'start', behavior })`, with `behavior` set to `'auto'` under
  `prefers-reduced-motion: reduce` and `'smooth'` otherwise;
- then calls `focus({ preventScroll: true })`.

The relevant-issues heading gets `tabIndex={-1}`, so screen readers and keyboard users start
from the issues.

The scroll runs once per location key, so later re-renders don't yank the page.
`RecommendationDetailPage` passes `recommendation.isSuccess`.

Alternative rejected: React Router `<ScrollRestoration>`. It handles hashes only for content
that is present at navigation time, not content that arrives after a query loads.

### D6. Invalid ids short-circuit (F-6)

Both detail pages parse the param with `Number.isInteger(n) && n > 0` before calling the query
hook. They render a not-found block before the `isPending` check, in the same shape as their
existing 404 message (`role="alert"` text plus "Back to your dashboard"):
- "This link doesn't point to a recommendation."
- "This link doesn't point to an issue."

The query hook stays disabled, so nothing is requested.

### D7. Saved and hidden lists with `useInfiniteQuery` (F-2)

- `useSaved` and `useDismissed` become infinite queries over `?page=N&page_size=50`. The page
  size is 50 (the server maximum is 100), which keeps the first paint small.
- `getNextPageParam` reads `next`.
- `SavedPage` flattens `data.pages` and shows an outline "Show more" button under each list
  while `hasNextPage`. The button is disabled during `isFetchingNextPage`, and its label stays
  "Show more" so it doesn't change width.
- Keys stay `savedKey` and `dismissedKey`, so existing invalidations still work: TanStack
  refetches every loaded page in sequence, and the entries already shown stay.
- An entry removed from page 1 shifts later pages by one, and the refetch accounts for that.

Alternative rejected: numbered pages, as on the dashboard. These are personal lists that
people scan and act on, with no ranking, and "Show more" keeps everything already seen on
screen.

### D8. Language shares from bytes (H-17)

`languageRows` computes the total from `bytes` and every row's `share` as `bytes / total`,
`Other` included. `LanguageChart`'s `percent` shows `<1%` for `0 < share < 0.005`.

The backend's rounded `share` stays in the API for other callers. The spec scenario with
Python 8000 / TypeScript 3000 bytes (0.73 / 0.27) is unchanged.

### D9. Browser tests: Playwright against the real backend (H-18)

- **Settings.** `config/settings/e2e.py` inherits `base`, then overrides:
  - every Redis-dependent value: `CACHES` locmem, `CELERY_TASK_ALWAYS_EAGER = True`, broker
    `memory://`;
  - the database name, `contribfinder_e2e`;
  - `GITHUB_API_BASE_URL` and `GITHUB_OAUTH_BASE_URL`, pointed at `http://127.0.0.1:9`, so an
    accidental GitHub call fails at once;
  - `INSTALLED_APPS += ["e2e"]`.

  A `.env` therefore can't change it.
- **Seeding.** App `apps/backend/e2e/` has the management command
  `e2e_seed --out <file>`. It:
  - flushes the e2e database;
  - creates users `e2e-dashboard`, `e2e-delete` and `e2e-unsynced`. Mutating specs each own a
    user, so specs can run in any order;
  - for synced users, builds data with the existing test helpers (dev dependency). It
    creates:
    - own repositories through `tests/profile_data.add_repo` and `synced`;
    - candidates through `tests/repo_fixtures.make_candidate_repo` and `add_candidate`;
    - issues through `make_issue`.

    It then runs `ProfileAnalysisService` and `RecommendationService` inline. Profile and
    recommendations are therefore real pipeline output, and a restore regenerates the same
    result. The pool holds more than 20 recommendable candidates, so pagination and filters
    show;
  - creates a `SessionStore` session per user (`_auth_user_id`, backend, hash) and writes
    `{username: sessionid}` JSON.

  The app doesn't exist under any other settings module, so production has no login path
  without GitHub.
- **Playwright.** `apps/frontend/playwright.config.ts`:
  - two `webServer` entries:
    - `scripts/e2e-backend.mjs`: `e2e_seed`, which creates the database if missing,
      migrates and seeds, then Django `runserver 127.0.0.1:8001 --noreload`, both with
      `--settings config.settings.e2e`, finding uv as `npm start` does;
    - Vite on `5174` with `VITE_API_PROXY_TARGET=http://127.0.0.1:8001`.

    These ports avoid the `npm start` stack. The seed runs in the backend server's command,
    not in `globalSetup`, because Playwright starts web servers before global setup. The
    sessions file is `e2e/.sessions.json` (gitignored);
  - each spec adds its user's `sessionid` cookie with `context.addCookies`;
  - specs live in `apps/frontend/e2e/*.spec.ts`;
  - Vitest excludes `e2e/`;
  - ESLint and `tsconfig.node.json` include it.
- **Flows.** These are the spec's list:
  - sign-in start: `page.request.get('/api/v1/auth/github', { maxRedirects: 0 })`, then assert
    a 302 to the GitHub authorize URL with `state`;
  - session end: clear cookies, trigger a refetch (navigate within the app), then expect the
    notice;
  - hash scroll: the heading is in the viewport and is `document.activeElement`.
- **CI.** Job `e2e` with a `pgvector/pgvector:pg16` service, `uv sync --frozen`, `npm ci`,
  `npx playwright install --with-deps chromium`, then `npm run e2e`. The report is uploaded on
  failure.

Alternatives rejected:
- `page.route` mocks against Vite only: fast, but it repeats the mocked unit tests, which is
  the gap H-18 names.
- A test-only login endpoint: a backdoor that could ship by mistake. A seed command, in an app
  only one settings module installs, cannot be reached over HTTP.
- Docker Compose for e2e: Docker isn't available on the dev machine (K-2).

## Risks / Trade-offs

- [Seeding through `tests/` helpers ties e2e to test code] → They are already the maintained
  way to build valid rows. Using them keeps the seed short and keeps it in step with model
  changes. The `e2e` app only runs where dev dependencies are installed.
- [Windows: Playwright's `webServer` may leave `python` children running] → On Windows
  Playwright stops a web server with `taskkill /T`, and `scripts/e2e-backend.mjs` runs Django
  through `scripts/child.mjs`, which also kills the process tree. Checked: no process is left
  after a local run. CI is Linux.
- [The `onUnauthenticated` flag could suppress a later, real session end] → It resets on
  every successful `/auth/me`, which a new sign-in always performs.
- [Infinite-query refetch after removing an entry re-requests every loaded page] → At most a
  few requests of 50. That is acceptable for an explicit user action.
- [Retrying 5xx with no backoff in tests could hide slowness] → Tests set `retryDelay: 0`
  only; production keeps the exponential default.
- [E2E adds about 2–3 minutes to CI] → It runs in parallel with the backend and frontend jobs.

## Migration Plan

Frontend and CI only, plus a backend app that production doesn't install. No data migration,
no API change. Roll back by reverting the commit.

## Open Questions

- Whether to add Firefox to the CI matrix once the suite is stable. It can be decided later
  without changing the specs.
