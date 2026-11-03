## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Failed refresh keeps the page
Once a page has shown data, a failed refetch of that data (a 5xx after its retries, or a network
error) SHALL NOT replace what is shown with an error or an empty state; the shown data stays
until a later fetch succeeds or the session ends. This SHALL hold for the sync status on the
dashboard and onboarding, and for the developer profile, skills, interests and repositories on
the dashboard. A load that fails before any data was shown SHALL show an error message, never an
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
loading; a signed-in user opening `/` or an unknown path SHALL go to the dashboard without seeing
"Continue with GitHub" first. Once the identity request answers 401 or fails, the sign-in page
SHALL show as before.

#### Scenario: Signed-in user opens the root
- **WHEN** a signed-in user opens `/` and the identity request has not answered yet
- **THEN** no "Continue with GitHub" button is shown, and the user lands on the dashboard once it answers

#### Scenario: Signed-out visitor
- **WHEN** a signed-out visitor opens `/` and the identity request answers 401
- **THEN** the sign-in page with "Continue with GitHub" is shown
