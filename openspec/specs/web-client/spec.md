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
remount or navigating back to the dashboard. A status with no job (for example after the user's
GitHub data was deleted) SHALL NOT trigger anything. Each status fetch SHALL trigger at most one
reaction, however many components display that status; a status fetch that is cancelled before
it completes SHALL trigger nothing, and leaving the signed-in pages SHALL cancel status requests
in flight. A job that starts and finishes between two status fetches SHALL still trigger it. When
the user starts a sync, a status answer fetched before the start SHALL NOT replace the started
job, so its progress is polled until it finishes. A finished sync or generation SHALL refetch the
data versions (see "Refresh derived data by data versions"), never the derived data directly, and
a finished sync SHALL also refetch the discovery and generation statuses. A finished discovery
changes no data area, so it SHALL refetch only the generation status. It SHALL NOT refetch the
status query that triggered it.

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

#### Scenario: Job gone after deleting GitHub data
- **WHEN** the sync status showed a COMPLETED job and, after the user deletes their GitHub data, it answers with no job
- **THEN** neither the data versions nor the discovery and generation statuses are refetched because of it

#### Scenario: Status fetch cancelled and restarted
- **WHEN** a status fetch that will return a newly finished job is cancelled by a refetch of the same status, and the new fetch returns the same job
- **THEN** the job's refresh runs once

#### Scenario: Older status answer after starting a sync
- **WHEN** a sync status fetch is in flight, the user starts a sync, and that fetch would answer with the previous finished job
- **THEN** the started job stays shown and its status keeps being polled until it finishes

### Requirement: Refresh derived data by data versions
While a user is signed in, the SPA SHALL keep one data versions query (`GET /api/v1/sync/versions`). It SHALL fetch it when the signed-in layout mounts, on window focus, on every route change and after a finished job (see "Refresh derived data on job transitions"). A route change is a navigation to a different path, query or fragment than the previous route, including Back or Forward to a page visited before (the first one included); a navigation that changes only the history state is not one. For each area whose time differs from the time in the previous versions fetch, it SHALL refetch that area's queries once:
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

#### Scenario: Back to the first page
- **WHEN** the user opens the dashboard, then a recommendation, then goes Back to the dashboard
- **THEN** the data versions are fetched again on the way back

#### Scenario: State-only navigation
- **WHEN** a page replaces its history entry with the same path, query and fragment and different state (for example after a dismiss)
- **THEN** the data versions are not fetched because of it

### Requirement: Retry policy
The SPA SHALL retry a failed data request only when it failed without a response (network
error) or with a 5xx status, at most twice. A 4xx response SHALL NOT be retried; its result SHALL
be shown as soon as it arrives. A successful response whose body cannot be read SHALL NOT be
retried. Mutations SHALL NOT be retried. Automated tests SHALL use the same retry rules as
production.

#### Scenario: Profile not analyzed yet
- **WHEN** `GET /api/v1/profile` answers `404 not_analyzed`
- **THEN** one request is made and the page shows the profile-being-prepared message without waiting

#### Scenario: Server error
- **WHEN** a request fails with 503 and then succeeds
- **THEN** the data is shown after the retry

#### Scenario: Throttled
- **WHEN** a request answers 429
- **THEN** it is not retried

#### Scenario: Unreadable success body
- **WHEN** a data request answers 200 with a body that is not JSON (for example an HTML page)
- **THEN** it is not retried and fails with code `invalid_response`

### Requirement: Ended session returns to sign-in
When any API request answers 401 while the user is signed in to the SPA, the SPA SHALL discard
all cached user data and go to the sign-in page. This SHALL include a refresh of the signed-in
user's identity that answers 401 after it had succeeded. The sign-in page SHALL then say that the
session ended and ask the user to sign in again. A 401 on the sign-in page itself (the normal
signed-out state) SHALL NOT show that notice. A failed refresh of the identity that is not a 401
SHALL NOT replace the signed-in pages while an identity is known. While the user's own sign-out
is pending, a 401 from another request SHALL NOT show the notice; if that sign-out then fails, a
401 seen meanwhile SHALL end the session as above. If going to the sign-in page fails, a later
401 SHALL still end the session.

#### Scenario: Session expired while on the dashboard
- **WHEN** the session expires and the next request from the dashboard answers 401
- **THEN** the user is on the sign-in page with a notice that the session ended, and no cached profile data remains

#### Scenario: Session ended during a mutation
- **WHEN** the user clicks Save and the request answers 401
- **THEN** the user is on the sign-in page with the same notice

#### Scenario: Visiting signed out
- **WHEN** a signed-out visitor opens the sign-in page
- **THEN** no session-ended notice is shown

#### Scenario: Identity refresh answers 401
- **WHEN** the signed-in user's identity is refreshed and the request answers 401
- **THEN** the user is on the sign-in page with the session-ended notice

#### Scenario: Identity refresh fails for a moment
- **WHEN** the signed-in user's identity is refreshed and the request fails with 503 after its retries
- **THEN** the signed-in page stays as it was

#### Scenario: Sign-out fails after the session ended
- **WHEN** the user logs out, another request answers 401 while the logout is pending, and the logout then fails with a network error
- **THEN** the user is on the sign-in page with the session-ended notice

#### Scenario: Sign-out succeeds with a 401 in flight
- **WHEN** the user logs out, another request answers 401 while the logout is pending, and the logout succeeds
- **THEN** the user is on the sign-in page without the session-ended notice

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

### Requirement: Request failures
Every failed API call made by the SPA SHALL report an HTTP status (0 when no response arrived)
and a machine-readable code: the server's error code when the response carries the error
envelope, `http_error` when it does not, `network_error` when no response arrived, and
`invalid_response` when a successful response's body cannot be read. A `Retry-After` header in
seconds SHALL be reported with the failure whether or not the body carries the envelope. A
state-changing call that cannot obtain a CSRF token SHALL report the token request's own status
and code. Concurrent state-changing calls SHALL share one CSRF token request.

#### Scenario: Offline
- **WHEN** a request fails before any response arrives
- **THEN** it fails with status 0 and code `network_error`

#### Scenario: Throttled CSRF token request
- **WHEN** a save is made without a CSRF cookie and `GET /api/v1/auth/csrf/` answers 429 with the error envelope
- **THEN** the save fails with status 429 and the envelope's code, and the save request is not sent

#### Scenario: Concurrent mutations without a CSRF cookie
- **WHEN** two state-changing calls start while no CSRF cookie is set
- **THEN** one `GET /api/v1/auth/csrf/` is sent and both calls use its token

#### Scenario: Wait without an envelope
- **WHEN** a request answers 503 with a plain-text body and `Retry-After: 30`
- **THEN** it fails with code `http_error` and a wait of 30 seconds

### Requirement: Leaving the signed-in app
After the user logs out, disconnects GitHub or deletes their account, the SPA SHALL go to the
sign-in page without the session-ended notice and SHALL keep no cached user data. After the user
deletes their GitHub data, the SPA SHALL go to onboarding. Only one of these four actions SHALL
be in progress at a time: while one is pending, the others SHALL be unavailable. The sign-in page
SHALL show only its own messages for a sign-in error code; an unknown code SHALL show the
generic sign-in failure message.

#### Scenario: Log out
- **WHEN** a signed-in user logs out
- **THEN** the user is on the sign-in page with no notice, and no profile, recommendation or job data remains cached

#### Scenario: Delete GitHub data
- **WHEN** the user confirms "Delete GitHub data" and the request succeeds
- **THEN** the user is on the onboarding page

#### Scenario: One account action at a time
- **WHEN** "Delete account" is pending
- **THEN** "Delete GitHub data" and "Disconnect GitHub" cannot be started

#### Scenario: Unknown sign-in error code
- **WHEN** a visitor opens `/?auth_error=__proto__`
- **THEN** the sign-in page shows the generic sign-in failure message

### Requirement: Stalled job
The SPA SHALL keep treating a stalled job (`stalled: true`) as unfinished: it keeps polling its
status and does not react to it as a finished job. It SHALL tell the user that background work
stopped and resumes automatically, instead of the stage text of a running job. While the sync job
is stalled, the user SHALL be able to start a sync (the dashboard's Refresh, onboarding's Try
again).

#### Scenario: Sync stalled on the dashboard
- **WHEN** the sync status returns a RUNNING job with `stalled: true`
- **THEN** the dashboard shows that background work stopped and resumes automatically, and Refresh is enabled

#### Scenario: Stalled job resumes
- **WHEN** a stalled sync is later returned RUNNING with `stalled: false`, then COMPLETED
- **THEN** the stalled notice goes away, and the finished sync triggers the usual refresh once

#### Scenario: Sync stalled during onboarding
- **WHEN** the onboarding page shows a sync job with `stalled: true`
- **THEN** the page shows the stalled notice and a Try again button

#### Scenario: Discovery stalled
- **WHEN** the sync is finished and the discovery status returns a job with `stalled: true`
- **THEN** the dashboard shows the stalled notice instead of "Finding projects…"

### Requirement: Failed refresh keeps the page
Once a page has shown data, a failed refetch of that data (a 5xx after its retries, or a network
error) SHALL NOT replace what is shown with an error or an empty state; the shown data stays
until a later fetch succeeds or the session ends. This SHALL hold for the sync status on the
dashboard and onboarding, for the developer profile, skills, interests and repositories on
the dashboard, for the discovery card and the recommendation list, for the recommendation and
issue detail pages (an answer that the recommendation or issue no longer exists still ends that
page), and for the saved and hidden lists. A load that fails before any data was shown SHALL show an error message, never an
empty list that reads as "nothing found".

#### Scenario: One sync status poll fails
- **WHEN** the dashboard is showing and a sync status poll fails with 503 after its retries
- **THEN** the dashboard stays as it was, with no "Could not load" message

#### Scenario: Developer profile refetch fails
- **WHEN** the dashboard shows the summary and skills, and a refetch of the developer profile fails with 503 after its retries
- **THEN** the summary, skills, interests and languages stay shown

#### Scenario: Skills fail to load
- **WHEN** the dashboard loads and the skills request fails with 503 after its retries
- **THEN** the skills section says the skills could not be loaded instead of showing no skills

#### Scenario: Issue refetch fails
- **WHEN** the user reads an issue and a refetch of it fails with 503 after its retries
- **THEN** the issue stays shown

#### Scenario: Discovery status poll fails
- **WHEN** the dashboard shows the discovery card and a discovery status poll fails with 503 after its retries
- **THEN** the card stays as it was, with no "Could not load project discovery" message

#### Scenario: Saved list refetch fails
- **WHEN** the saved page shows saved and hidden projects and their refetch fails with 503 after its retries
- **THEN** both lists stay shown

#### Scenario: Issue no longer relevant
- **WHEN** the user reads an issue and a refetch of it answers 404
- **THEN** the page says the issue is no longer among the relevant issues

### Requirement: Sync start errors
When starting a sync fails, the dashboard and onboarding SHALL show the same message for the same
error. For a `sync_cooldown` rejection with a `Retry-After` time, the message SHALL say from what
clock time a refresh is possible, computed when the rejection arrived, so it stays true while it
is shown.

#### Scenario: Cooldown on the dashboard
- **WHEN** the user presses Refresh at 14:01 and the start answers 429 `sync_cooldown` with `Retry-After: 240`
- **THEN** the dashboard says a refresh is possible again after 14:05

#### Scenario: Cooldown on onboarding
- **WHEN** onboarding shows a stalled sync, the user presses Try again, and the start answers 429 `sync_cooldown` with `Retry-After: 240`
- **THEN** onboarding shows the same cooldown message as the dashboard

### Requirement: Sign-in page while the identity loads
The sign-in page SHALL NOT show its sign-in button while the signed-in user's identity is still
loading (it SHALL show a loading message instead, never a blank page); a signed-in user opening `/` or an unknown path SHALL go to the dashboard without seeing
"Continue with GitHub" first. Once the identity request answers 401 or fails, the sign-in page
SHALL show as before.

#### Scenario: Signed-in user opens the root
- **WHEN** a signed-in user opens `/` and the identity request has not answered yet
- **THEN** no "Continue with GitHub" button is shown, and the user lands on the dashboard once it answers

#### Scenario: Signed-out visitor
- **WHEN** a signed-out visitor opens `/` and the identity request answers 401
- **THEN** the sign-in page with "Continue with GitHub" is shown

### Requirement: Pipeline progress display
The dashboard's pipeline stage (syncing, analyzing, finding projects, preparing recommendations,
stalled) SHALL follow the discovery and recommendation statuses whether or not the discovery card
and the recommendation list are shown, for example while the profile is not yet analyzed. A stalled job SHALL NOT be described as progressing anywhere: the discovery card SHALL
show the stalled notice instead of "Finding projects…", and a sync step that is running in a
stalled job SHALL show as stopped, not as an animated "In progress". A step state the interface
does not know SHALL be shown as waiting and SHALL NOT break the page. A relative time ("updated 5
minutes ago") SHALL advance while it is shown, SHALL never be in the future, and SHALL be
formatted in the browser's language like other dates. Every page that shows a GitHub failure code
SHALL use the same reason for it, and a sync start rejected because GitHub is not connected SHALL
offer "Sign in with GitHub again".

#### Scenario: Discovery while the profile is not shown
- **WHEN** the developer profile is not analyzed yet and a discovery run is RUNNING
- **THEN** the dashboard shows "Finding projects…" and polls the discovery status until it finishes

#### Scenario: Stalled discovery card
- **WHEN** the discovery status returns a RUNNING job with `stalled: true`
- **THEN** the discovery card shows the stalled notice, matching the header

#### Scenario: Stalled step
- **WHEN** onboarding shows a stalled sync whose repositories step is running
- **THEN** that step shows as stopped without a spinner, next to the stalled notice

#### Scenario: Unknown step state
- **WHEN** a sync step has a state the interface does not know
- **THEN** that step shows as waiting and the rest of the page renders

#### Scenario: Relative time advances
- **WHEN** the discovery card says "updated this minute" and an hour passes without a new status
- **THEN** it says "updated 1 hour ago"

#### Scenario: Not connected on start
- **WHEN** onboarding's Start sync is answered 409 `github_not_connected`
- **THEN** the page shows the not-connected message and "Sign in with GitHub again"

### Requirement: Render failures and dead ends
An error while rendering a signed-in page SHALL show a page that says something went wrong and
offers to reload and a way back to the dashboard, never the router's default error screen. A
stored time the browser cannot read SHALL be shown as "Unknown" and SHALL NOT break the page.
A page that cannot show what was asked for (a recommendation or issue that no longer exists, or a
first load that failed) SHALL have a heading, SHALL move keyboard focus to it when it replaces
content during a visit, and, for a failed load, SHALL offer to try the load again. While a first
load that failed is being retried, the page SHALL show that it is loading, not the failure
message. Returning to a page through the browser history SHALL NOT scroll to or focus the URL's
section again when that page already did so for that history entry; opening or reloading a link
with a section SHALL still scroll to it. A detail value SHALL wrap instead of widening the page.

#### Scenario: Unreadable time
- **WHEN** a saved project's save time is not a valid time
- **THEN** the saved page shows the project with the time "Unknown"

#### Scenario: Render error
- **WHEN** a component on the dashboard throws while rendering
- **THEN** the page says something went wrong and offers Reload and the way back to the dashboard

#### Scenario: Recommendation gone during a visit
- **WHEN** the user has focused Save on a recommendation page and a refetch answers 404
- **THEN** the page shows the "no longer exists" heading with keyboard focus on it

#### Scenario: Retry after a failed first load
- **WHEN** a recommendation page's first load failed and the user chooses Try again
- **THEN** the page shows that it is loading, then the recommendation when the load succeeds

#### Scenario: Back to a section link
- **WHEN** the user opened `/app/recommendations/5#relevant-issues`, scrolled to the top, opened an issue and went Back
- **THEN** the recommendation page does not scroll to or focus the relevant issues again
