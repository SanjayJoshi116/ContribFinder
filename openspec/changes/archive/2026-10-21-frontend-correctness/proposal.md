## Why

The SPA often contradicts the server, or just stalls. Batch 9 of `Bug_Backlog.md` (verified)
found these problems:
- the dashboard refetches everything on every focus;
- normal 404s take seconds to show;
- an expired session looks like a broken page;
- links and pages strand the user on "Loading…" or a dead page;
- the profile chart drops small languages.

None of the main flows runs in a real browser against the real backend, so these bugs got past
every check.

This is theme 9 ("frontend cache churn") of the backlog plus the frontend gaps of themes 5 and
7. It changes no ranking, so it does not wait for K-1.

## What Changes

- **Fetch on change, not on every look.**
  - A sync, discovery or generation job refreshes the data derived from it only when the
    job's id or status changes to finished, never because a completed job was seen again
    (F-1). For example, focusing the window or coming back from a detail page refetches only
    the status.
  - The refresh runs once per status fetch, not once per component that watches the status
    (F-9).
- **Fail fast on client errors.**
  - Queries retry only network failures and 5xx responses, at most twice. A 4xx, including
    `404 not_analyzed`, 401 and 429, shows its result at once (H-5).
  - Tests use the same client policy as production.
- **An ended session returns to sign-in.**
  - Any 401 from the API, on a query or a mutation, clears cached user data. The SPA goes to
    the sign-in page, which says the session ended and asks the user to sign in again (F-7).
- **Navigation always lands somewhere.**
  - A `?page=N` past the last page moves to a page that exists instead of showing a dead
    error (F-3).
  - Dismissing the last card on a page moves back one page instead of saying there are no
    recommendations (F-3).
  - "N relevant issues" scrolls to and focuses the relevant issues once the detail page has
    loaded (F-5). The scroll is instant when the user prefers reduced motion.
  - A recommendation or issue URL with an id that is not a positive integer says the link
    doesn't point to anything, instead of "Loading…" forever (F-6).
- **Saved and hidden lists show everything.** Both lists load in pages with a "Show more"
  control, so a user with more than 100 entries can see and restore all of them (F-2).
- **Undo keeps its time.** Changing a filter no longer restarts the 10-second Undo window
  after a dismissal (F-8).
- **Language chart from bytes.**
  - "Other" and every share are computed from bytes, not from shares the server already
    rounded (H-17).
  - A language below 1% shows as "<1%", never "0%".
- **Browser tests for the main flows (H-18).**
  - Playwright runs against the real Django backend and PostgreSQL with seeded users. It
    covers:
    - sign-in start (redirect to GitHub with a state);
    - an unsynced user landing on onboarding;
    - the dashboard;
    - save, then the saved page;
    - dismiss and undo;
    - the relevant-issues link;
    - session end;
    - delete GitHub data.
  - Seeding lives in a Django app that only the end-to-end settings install. Production has no
    login backdoor.
  - CI gets an `e2e` job.

## Capabilities

### New Capabilities

- `web-client`: SPA-wide server-state behavior:
  - when derived data is refreshed;
  - the retry policy;
  - handling an ended session;
  - end-to-end coverage of the main flows.

### Modified Capabilities

- `recommendations-view`:
  - list pages past the end recover;
  - the relevant-issues link scrolls to the issues;
  - an invalid recommendation id shows not-found.
- `recommendation-feedback`:
  - saved and hidden lists are paginated with "Show more";
  - the Undo window is not restarted by filter changes.
- `issue-matching`: an invalid issue id on the issue detail page shows not-found.
- `developer-profile`: the languages chart computes "Other" and shares from bytes and shows
  "<1%" for small languages.

## Impact

- **Frontend:**
  - `main.tsx` and a new `src/app/queryClient.ts` (client factory: retry policy, 401 handling);
    `test/render.tsx` uses the factory.
  - `features/sync/api.ts`, `features/recommendations/api.ts`, `features/sync/pipeline.ts`:
    transition-based refresh, run inside the status query.
  - `features/recommendations/RecommendationList.tsx`: page recovery and Undo.
  - `RecommendationDetailPage.tsx`, `RelevantIssues.tsx`, `IssueDetailPage.tsx`: hash scroll and
    invalid id.
  - `features/feedback/api.ts`, `SavedPage.tsx`: infinite queries with "Show more".
  - `features/feedback/RecommendationActions.tsx` (`DismissUndo`).
  - `features/profile/languages.ts`, `LanguageChart.tsx`.
  - `features/auth/authErrors.ts` and `LandingPage.tsx`: the `session_ended` notice.
  - New `apps/frontend/e2e/`, `playwright.config.ts`, `@playwright/test` dev dependency and an
    `npm run e2e` script.
- **Backend:**
  - A new `e2e` Django app (management command `e2e_seed`), installed only by the new
    `config/settings/e2e.py`. It points GitHub at an unreachable address and runs tasks inline.
  - No API or model change. The OpenAPI schema is unchanged.
- **CI:** a new `e2e` job in `.github/workflows/ci.yml` (PostgreSQL service, Chromium).
- **Ranking:** none.
- **Visual design:**
  - No restyling. The new states (session ended, not found, "Show more", page recovery) use
    the existing tokens and components.
  - Their copy follows the interface's voice: plain, active, and it says what to do next.
- **Out of scope:**
  - The OAuth callback against real GitHub (it needs a live GitHub app).
  - Starting a sync in end-to-end tests (it calls GitHub).
  - Dev scripts and checks (batch 10).
  - Cleanup (batch 11).
