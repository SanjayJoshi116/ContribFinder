## MODIFIED Requirements

### Requirement: Refresh derived data on job transitions
The SPA SHALL refetch data derived from a sync, discovery or recommendation generation job only
when it sees that job's id or status change to a finished state, compared with the last status
it fetched. Seeing the same finished job again SHALL NOT refetch derived data, for example after
a window focus, a remount or navigating back to the dashboard. Each status fetch SHALL trigger at
most one refresh, however many components display that status. A job that starts and finishes
between two status fetches SHALL still trigger the refresh. A finished generation SHALL also
refresh the developer profile, skills and interests, because every profile analysis ends in a
generation, including one that no sync started; it SHALL NOT refetch the job status queries
themselves.

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

#### Scenario: Profile re-analyzed without a sync
- **WHEN** an operator re-analyzes the user's profile while the dashboard is open, and the generation that follows finishes
- **THEN** the developer profile, skills and interests are refetched once together with the recommendations, and the sync status is not refetched by that refresh
