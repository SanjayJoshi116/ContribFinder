## MODIFIED Requirements

### Requirement: Synced data endpoints
The system SHALL expose the requesting user's synced GitHub profile, including whether a profile README exists, and a paginated list of the repositories they own with languages and topics. These SHALL be served from stored data without calling GitHub. Repositories linked to the user only as contributor SHALL NOT appear in the repository list. A client SHALL be able to request a page as large as the per-sync repository cap (at least 100), and the dashboard SHALL show every synced repository.

#### Scenario: Profile data
- **WHEN** a signed-in user with a completed sync requests `GET /api/v1/profile/github`
- **THEN** the response contains their stored GitHub profile fields and `has_profile_readme`, and no GitHub request is made

#### Scenario: Repository list
- **WHEN** the user requests `GET /api/v1/profile/repositories`
- **THEN** the response is a paginated list of the repositories they own, each with metadata, languages (with byte counts) and topics, most recently pushed first

#### Scenario: Contributed repositories excluded
- **WHEN** the user owns 2 repositories and is linked to 3 others as contributor
- **THEN** the repository list contains only the 2 owned repositories

#### Scenario: Cap above 100
- **WHEN** the per-sync repository cap is 200 and a user has 150 owned repositories synced
- **THEN** one request with a page size of 200 returns all 150, and the dashboard lists all 150

#### Scenario: Not yet synced
- **WHEN** a user with no completed sync requests `GET /api/v1/profile/github`
- **THEN** the system responds with HTTP 404 and error code `not_synced`
