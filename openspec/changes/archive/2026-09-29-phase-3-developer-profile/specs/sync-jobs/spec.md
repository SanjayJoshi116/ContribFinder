## MODIFIED Requirements

### Requirement: Job lifecycle and progress
Each sync job SHALL move through PENDING → RUNNING → COMPLETED, or into FAILED, RETRYING or CANCELLED. It SHALL record start time, completion time, attempt count, a machine-readable error code on failure, and per-step status for the steps profile, readme, repositories, languages, topics, dependencies, contributions and analysis, in that order. Each step's status SHALL be pending, running, done, not_found, skipped or failed. Jobs created before the dependencies, contributions and analysis steps existed SHALL still be readable, and a missing step SHALL be reported as pending.

#### Scenario: Successful job
- **WHEN** a sync runs to completion
- **THEN** the job status is COMPLETED, every step is done, not_found or skipped, and the start and completion times are set

#### Scenario: Failed job keeps partial progress
- **WHEN** the languages step fails permanently after profile and repositories completed
- **THEN** the job status is FAILED with an error code, the profile and repositories steps stay done, the languages step is failed, and the data from completed steps is kept

#### Scenario: Analysis failure
- **WHEN** every GitHub step completes but the analysis step fails
- **THEN** the job status is FAILED with error code `analysis_failed`, the analysis step is failed, the synced GitHub data is kept, and the previous developer profile is unchanged

### Requirement: Synced data endpoints
The system SHALL expose the requesting user's synced GitHub profile, including whether a profile README exists, and a paginated list of the repositories they own with languages and topics. These SHALL be served from stored data without calling GitHub. Repositories linked to the user only as contributor SHALL NOT appear in the repository list.

#### Scenario: Profile data
- **WHEN** a signed-in user with a completed sync requests `GET /api/v1/profile/github`
- **THEN** the response contains their stored GitHub profile fields and `has_profile_readme`, and no GitHub request is made

#### Scenario: Repository list
- **WHEN** the user requests `GET /api/v1/profile/repositories`
- **THEN** the response is a paginated list of the repositories they own, each with metadata, languages (with byte counts) and topics, most recently pushed first

#### Scenario: Contributed repositories excluded
- **WHEN** the user owns 2 repositories and is linked to 3 others as contributor
- **THEN** the repository list contains only the 2 owned repositories

#### Scenario: Not yet synced
- **WHEN** a user with no completed sync requests `GET /api/v1/profile/github`
- **THEN** the system responds with HTTP 404 and error code `not_synced`

### Requirement: Onboarding progress view
After sign-in, a user without a completed sync SHALL see an onboarding view. It SHALL show per-step progress for every sync step (profile, README, repositories, languages, topics, dependencies, contributions and profile analysis) and update without a page reload until the sync ends, then show the profile page. If the sync fails, the view SHALL show a readable message and a way to retry.

#### Scenario: Onboarding completes
- **WHEN** a newly signed-in user's sync moves from RUNNING to COMPLETED
- **THEN** the onboarding view marks each step, including dependencies, contributions and analysis, as it completes and then shows the profile page

#### Scenario: Onboarding sync fails
- **WHEN** the sync ends as FAILED with `github_auth_invalid`
- **THEN** the view explains that GitHub access must be renewed and offers sign-in again

#### Scenario: Analysis fails during onboarding
- **WHEN** the sync ends as FAILED with `analysis_failed`
- **THEN** the view explains that the profile could not be built from the synced data and offers a retry
