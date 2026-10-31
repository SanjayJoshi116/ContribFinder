# web-client Specification

## Purpose

Defines how the single-page app keeps server state in step with the backend: when derived
data is refreshed, how failed requests are retried, what happens when the session ends, and
which flows are verified end to end in a real browser.
## Requirements
### Requirement: Refresh derived data on job transitions
The SPA SHALL react to a sync, discovery or recommendation generation job only when it sees that
job's id or status change to a finished state, compared with the last status it fetched. Seeing
the same finished job again SHALL NOT trigger anything, for example after a window focus, a
remount or navigating back to the dashboard. Each status fetch SHALL trigger at most one
reaction, however many components display that status. A job that starts and finishes between
two status fetches SHALL still trigger it. A finished sync or generation SHALL refetch the data versions (see
"Refresh derived data by data versions"), never the derived data directly, and a finished sync
SHALL also refetch the discovery and generation statuses. A finished discovery changes no data
area, so it SHALL refetch only the generation status. It SHALL NOT refetch the status query that triggered it.

#### Scenario: Discovery finishes
- **WHEN** the discovery status changes from RUNNING to COMPLETED
- **THEN** the generation status is refetched once and the data versions are not

#### Scenario: Returning to the dashboard
- **WHEN** the latest sync job is COMPLETED and the user goes from the dashboard to a recommendation and back
- **THEN** the sync status is fetched again, and skills, interests, repositories, recommendations and the saved list are not refetched

#### Scenario: Sync finishes
- **WHEN** the sync status changes from RUNNING to COMPLETED and the data versions then show new `github` and `profile` times
- **THEN** the data versions are refetched once, and the GitHub data and the developer profile, skills and interests are refetched once

#### Scenario: Short generation between polls
- **WHEN** a status fetch returns a COMPLETED generation job whose id was not in the previous fetch
- **THEN** the data versions are refetched once, and the recommendation list is refetched once because `recommendations` changed

#### Scenario: Two components show the generation status
- **WHEN** the dashboard list and the pipeline indicator both display the generation status and the job finishes
- **THEN** the data versions are fetched once and the recommendation list once, not twice

#### Scenario: Generation without a profile change
- **WHEN** a generation started by the beat sweep finishes and the profile was not re-analyzed
- **THEN** the recommendation list is refetched, and the developer profile, skills and interests are not

#### Scenario: Profile re-analyzed without a sync
- **WHEN** an operator re-analyzes the user's profile while the dashboard is open, and the generation that follows finishes
- **THEN** the data versions show new `profile` and `recommendations` times, the developer profile, skills and interests and the recommendations are each refetched once, and the sync status is not refetched by that refresh

### Requirement: Refresh derived data by data versions
While a user is signed in, the SPA SHALL keep one data versions query (`GET /api/v1/sync/versions`). It SHALL fetch it when the signed-in layout mounts, on window focus, on every route change and after a finished job (see "Refresh derived data on job transitions"). For each area whose time differs from the time in the previous versions fetch, it SHALL refetch that area's queries once:
- `github`: the GitHub profile and the synced repositories;
- `profile`: the developer profile, skills and interests;
- `recommendations`: the recommendation list and details, issue details, the saved list and the hidden list (it shows the stored repository data).

The first versions fetch after sign-in, or after the user's data was deleted, SHALL refetch nothing (the derived data loads on its own). Each versions fetch SHALL refetch each changed area at most once, however many components are mounted, also when a new versions fetch starts while another is running. A failed versions fetch SHALL refetch nothing. The default stale time and the invalidations of the user's own actions (save, dismiss, restore, delete) SHALL stay as they are.

#### Scenario: Repository refreshed in the background
- **WHEN** the backend refreshes the issues of a recommended repository while the user reads a recommendation, and the user then opens another page
- **THEN** the data versions show a new `recommendations` time and the recommendation queries are refetched once, and the profile queries are not

#### Scenario: Analysis whose discovery fails
- **WHEN** the user's profile is re-analyzed and the discovery after it fails, and the user returns to the window
- **THEN** the developer profile, skills and interests are refetched once, and the recommendations are not

#### Scenario: Nothing changed
- **WHEN** the user switches between pages and the data versions are unchanged
- **THEN** no derived query is refetched because of them

#### Scenario: Two jobs finish together
- **WHEN** the sync and the generation finish within one poll interval and both refetch the data versions
- **THEN** each changed area is refetched once

#### Scenario: First fetch
- **WHEN** the signed-in layout mounts and fetches the data versions for the first time
- **THEN** no derived query is refetched because of them

### Requirement: Retry policy
The SPA SHALL retry a failed data request only when it failed without a response (network
error) or with a 5xx status, at most twice. A 4xx response SHALL NOT be retried; its result SHALL
be shown as soon as it arrives. Mutations SHALL NOT be retried. Automated tests SHALL use the same
retry rules as production.

#### Scenario: Profile not analyzed yet
- **WHEN** `GET /api/v1/profile` answers `404 not_analyzed`
- **THEN** one request is made and the page shows the profile-being-prepared message without waiting

#### Scenario: Server error
- **WHEN** a request fails with 503 and then succeeds
- **THEN** the data is shown after the retry

#### Scenario: Throttled
- **WHEN** a request answers 429
- **THEN** it is not retried

### Requirement: Ended session returns to sign-in
When any API request answers 401 while the user is signed in to the SPA, the SPA SHALL discard
all cached user data and go to the sign-in page. The sign-in page SHALL then say that the session
ended and ask the user to sign in again. A 401 on the sign-in page itself (the normal signed-out
state) SHALL NOT show that notice.

#### Scenario: Session expired while on the dashboard
- **WHEN** the session expires and the next request from the dashboard answers 401
- **THEN** the user is on the sign-in page with a notice that the session ended, and no cached profile data remains

#### Scenario: Session ended during a mutation
- **WHEN** the user clicks Save and the request answers 401
- **THEN** the user is on the sign-in page with the same notice

#### Scenario: Visiting signed out
- **WHEN** a signed-out visitor opens the sign-in page
- **THEN** no session-ended notice is shown

### Requirement: End-to-end coverage of the main flows
The project SHALL have browser tests that run the built SPA against the real backend and a real
PostgreSQL database, with data seeded by a command that only the end-to-end configuration
provides. The built SPA SHALL be the production build, served as built with its Content
Security Policy, not the development server; a development-server run MAY be offered for local
use only, and CI SHALL NOT use it. A test SHALL fail when the page reports a Content Security
Policy violation. The production configuration SHALL NOT offer any way to sign in without
GitHub. The tests SHALL make no request to GitHub, and SHALL cover at least:
- the sign-in start redirecting to GitHub with a state;
- a signed-in user without synced data landing on onboarding;
- a synced user's dashboard with profile and recommendations;
- save, then the saved-projects page;
- dismiss and undo;
- following the relevant-issues link to the issues on the detail page;
- an ended session returning to sign-in;
- deleting GitHub data returning to onboarding.

CI SHALL run these tests on every pull request and push to main. The seed command SHALL refuse to
run against any database other than the end-to-end one, and SHALL leave no data from an earlier
run (users, sessions, audit entries, repositories). Every test that changes data SHALL sign in as
a user that no other test uses, and a retried attempt of such a test SHALL start from seeded data.

#### Scenario: Seeding outside the end-to-end configuration
- **WHEN** the seed command is invoked under the development, test or production settings
- **THEN** it does not exist there

#### Scenario: CI run
- **WHEN** a pull request is opened
- **THEN** CI runs the browser tests against the production build and fails the build if any of the listed flows fails

#### Scenario: Policy violation fails a test
- **WHEN** a change makes a page load a script, image or connection from an origin the built app's policy does not allow
- **THEN** the browser test that opens that page fails, naming the violation

#### Scenario: Seeding another database
- **WHEN** the seed command runs with the end-to-end configuration installed but a default database other than the end-to-end one
- **THEN** it stops with an error before deleting or writing anything

#### Scenario: Retried test that changes data
- **WHEN** a test that saves, dismisses or deletes data fails after changing it and CI runs it again
- **THEN** the retry signs in as a user with the seeded data, unchanged by the first attempt

### Requirement: Content Security Policy in the built app
The production build of the SPA SHALL declare a Content Security Policy in its `index.html` that allows scripts and network connections only from the same origin, images only from the same origin, `data:` URLs and GitHub avatars (`https://avatars.githubusercontent.com`), styles from the same origin and inline style attributes, and SHALL forbid plugins (`object-src 'none'`) and `<base>` (`base-uri 'none'`). The built app SHALL work under it without policy violations. The development server SHALL NOT add the policy.

#### Scenario: Built index
- **WHEN** the SPA is built for production
- **THEN** `dist/index.html` contains a `Content-Security-Policy` meta tag with `script-src 'self'`, `connect-src 'self'`, `object-src 'none'` and `base-uri 'none'`, and no inline script

#### Scenario: Dashboard under the policy
- **WHEN** a signed-in user opens the dashboard of the built app, with its avatar, language chart and recommendations
- **THEN** every resource loads and the browser reports no Content Security Policy violation

#### Scenario: Development server
- **WHEN** the SPA runs on the Vite development server
- **THEN** `index.html` carries no Content Security Policy and hot reload works

