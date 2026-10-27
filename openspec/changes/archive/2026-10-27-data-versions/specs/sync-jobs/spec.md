## ADDED Requirements

### Requirement: Data versions endpoint
The system SHALL provide, for the requesting user only, when each area of their derived data last changed, as a time or null when the area holds no data:
- `github`: the end of their last completed sync;
- `profile`: the time their developer profile was last analyzed;
- `recommendations`: the latest of the end of their last completed recommendation generation and the newest stored data time (metadata, README, community files, dependencies, activity, issues) of any repository they have a recommendation or a saved entry for.

The endpoint SHALL read stored data only: it SHALL NOT call GitHub, start a job or change any row. It SHALL require authentication like every other endpoint and SHALL appear in the OpenAPI schema.

#### Scenario: Versions of a synced user
- **WHEN** a signed-in user whose last sync completed at 10:00, whose profile was analyzed at 10:01 and whose last generation completed at 10:03 requests `GET /api/v1/sync/versions`, and no recommended or saved repository has newer data
- **THEN** the response is `github` 10:00, `profile` 10:01 and `recommendations` 10:03

#### Scenario: Repository refreshed after the generation
- **WHEN** the backend refreshes the issues of a repository the user has a recommendation for at 10:20, after their last generation completed at 10:03
- **THEN** `recommendations` is 10:20, and `github` and `profile` are unchanged

#### Scenario: Analysis without a generation
- **WHEN** the user's profile is re-analyzed at 11:00 and the discovery that follows fails
- **THEN** `profile` is 11:00 and `recommendations` is unchanged

#### Scenario: Never synced
- **WHEN** a signed-in user who has never synced requests the versions
- **THEN** every area is null

#### Scenario: Another user's data is not counted
- **WHEN** user B's recommended repository is refreshed and user A requests the versions
- **THEN** user A's `recommendations` is unchanged, unless user A also has a recommendation or a saved entry for that repository

#### Scenario: Read only
- **WHEN** the versions are requested
- **THEN** no job is started and no stored row changes
