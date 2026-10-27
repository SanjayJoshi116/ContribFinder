## MODIFIED Requirements

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
