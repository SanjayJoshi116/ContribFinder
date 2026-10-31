## MODIFIED Requirements

### Requirement: Delete GitHub-derived data
A signed-in user SHALL be able to delete all GitHub-derived data (`DELETE /api/v1/profile/github-data`, CSRF-protected). The system SHALL first cancel the user's active jobs, then delete: the stored GitHub profile and profile README, the display name taken from GitHub, the user's repository links, the developer profile with its skills, interests and evidence, the candidate pool and discovery records, recommendations and reasons, saved and dismissed repositories, feedback events, the user's job history, and the user's cached GitHub responses. Shared repository data SHALL be deleted when no other user's link, candidate, recommendation, save or dismissal references it. The user account and the GitHub connection SHALL be kept, and the user SHALL be able to sync again from the start. Deletion SHALL be complete when the response is returned, and SHALL stay complete: background work that was running for the user when deletion started SHALL NOT write any of the deleted kinds of data afterwards. The deletion and its audit entry SHALL happen together or not at all.

#### Scenario: Data deleted
- **WHEN** a user with a synced profile, recommendations, saves and feedback deletes their GitHub data
- **THEN** none of that data exists afterwards, the user's display name is empty, the response is 204, and the user is still signed in with GitHub connected

#### Scenario: Shared repository kept for others
- **WHEN** a deleted user's candidate repository is also in another user's pool
- **THEN** the repository and its analysis are kept, and only the deleted user's rows are removed

#### Scenario: Sync again
- **WHEN** a user who deleted their GitHub data opens the dashboard
- **THEN** they are taken to onboarding, where a new sync starts only when they ask for it

#### Scenario: Running job finishes after deletion
- **WHEN** a profile sync, profile analysis, discovery or recommendation job is in the middle of a step while the user deletes their GitHub data, and the step finishes afterwards
- **THEN** the step writes nothing, the job ends as cancelled, and the user's GitHub profile, developer profile, repository links, candidates and recommendations still do not exist

#### Scenario: Recording the deletion fails
- **WHEN** writing the `github_data_deleted` audit entry fails during a GitHub data deletion
- **THEN** the response is an error, the user's GitHub-derived data still exists, and no `github_data_deleted` entry exists
