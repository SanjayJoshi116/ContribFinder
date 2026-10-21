# web-client Specification

## Purpose

Defines how the single-page app keeps server state in step with the backend: when derived
data is refreshed, how failed requests are retried, what happens when the session ends, and
which flows are verified end to end in a real browser.

## Requirements

### Requirement: Refresh derived data on job transitions
The SPA SHALL refetch data derived from a sync, discovery or recommendation generation job only
when it sees that job's id or status change to a finished state, compared with the last status
it fetched. Seeing the same finished job again SHALL NOT refetch derived data, for example after
a window focus, a remount or navigating back to the dashboard. Each status fetch SHALL trigger at
most one refresh, however many components display that status. A job that starts and finishes
between two status fetches SHALL still trigger the refresh.

#### Scenario: Returning to the dashboard
- **WHEN** the latest sync job is COMPLETED and the user goes from the dashboard to a recommendation and back
- **THEN** the sync status is fetched again, and skills, interests, repositories, recommendations and the saved list are not refetched

#### Scenario: Sync finishes
- **WHEN** the sync status changes from RUNNING to COMPLETED
- **THEN** the profile data and recommendations are refetched once

#### Scenario: Short generation between polls
- **WHEN** a status fetch returns a COMPLETED generation job whose id was not in the previous fetch
- **THEN** the recommendation list is refetched once

#### Scenario: Two components show the generation status
- **WHEN** the dashboard list and the pipeline indicator both display the generation status and the job finishes
- **THEN** the recommendation list is fetched once, not twice

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
provides. The production configuration SHALL NOT offer any way to sign in without GitHub. The
tests SHALL make no request to GitHub, and SHALL cover at least:
- the sign-in start redirecting to GitHub with a state;
- a signed-in user without synced data landing on onboarding;
- a synced user's dashboard with profile and recommendations;
- save, then the saved-projects page;
- dismiss and undo;
- following the relevant-issues link to the issues on the detail page;
- an ended session returning to sign-in;
- deleting GitHub data returning to onboarding.

CI SHALL run these tests on every pull request and push to main.

#### Scenario: Seeding outside the end-to-end configuration
- **WHEN** the seed command is invoked under the development, test or production settings
- **THEN** it does not exist there

#### Scenario: CI run
- **WHEN** a pull request is opened
- **THEN** CI runs the browser tests and fails the build if any of the listed flows fails
