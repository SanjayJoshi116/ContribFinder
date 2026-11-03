## MODIFIED Requirements

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
