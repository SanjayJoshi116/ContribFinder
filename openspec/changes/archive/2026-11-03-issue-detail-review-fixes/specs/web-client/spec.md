## MODIFIED Requirements

### Requirement: Failed refresh keeps the page
Once a page has shown data, a failed refetch of that data (a 5xx after its retries, or a network
error) SHALL NOT replace what is shown with an error or an empty state; the shown data stays
until a later fetch succeeds or the session ends. This SHALL hold for the sync status on the
dashboard and onboarding, for the developer profile, skills, interests and repositories on
the dashboard, and for the issue detail page (an answer that the issue is no longer relevant still
ends that page). A load that fails before any data was shown SHALL show an error message, never an
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

#### Scenario: Issue no longer relevant
- **WHEN** the user reads an issue and a refetch of it answers 404
- **THEN** the page says the issue is no longer among the relevant issues
