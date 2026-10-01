## Purpose

Gives developers control over the data ContribFinder keeps about them: refresh it, see what is stored and why, delete everything derived from GitHub, or delete their account entirely, with each sensitive action audited.

## ADDED Requirements

### Requirement: Refresh rebuilds the pipeline
Refreshing (`POST /api/v1/profile/sync`, subject to the existing cooldown) SHALL run the whole pipeline as tracked background jobs: GitHub sync, profile analysis, repository discovery and recommendation generation, each starting when the previous one completes. A failed stage SHALL stop the chain and keep the previous results of later stages. The dashboard SHALL show which stage is running (syncing, analyzing, finding projects, preparing recommendations) and update without a reload.

#### Scenario: Full refresh
- **WHEN** a user refreshes and every stage succeeds
- **THEN** a sync, a discovery and a recommendation generation job complete in that order, and the dashboard shows each stage while it runs

#### Scenario: Discovery fails
- **WHEN** the discovery stage of a refresh fails
- **THEN** no recommendation generation starts from it and the user's previous recommendations are unchanged

### Requirement: Delete GitHub-derived data
A signed-in user SHALL be able to delete all GitHub-derived data (`DELETE /api/v1/profile/github-data`, CSRF-protected). The system SHALL first cancel the user's active jobs, then delete: the stored GitHub profile and profile README, the user's repository links, the developer profile with its skills, interests and evidence, the candidate pool and discovery records, recommendations and reasons, saved and dismissed repositories, feedback events, the user's job history, and the user's cached GitHub responses. Shared repository data SHALL be deleted when no other user's link, candidate, recommendation, save or dismissal references it. The user account and the GitHub connection SHALL be kept, and the user SHALL be able to sync again from the start. Deletion SHALL be complete when the response is returned.

#### Scenario: Data deleted
- **WHEN** a user with a synced profile, recommendations, saves and feedback deletes their GitHub data
- **THEN** none of that data exists afterwards, the response is 204, and the user is still signed in with GitHub connected

#### Scenario: Shared repository kept for others
- **WHEN** a deleted user's candidate repository is also in another user's pool
- **THEN** the repository and its analysis are kept, and only the deleted user's rows are removed

#### Scenario: Sync again
- **WHEN** a user who deleted their GitHub data opens the dashboard
- **THEN** they are taken to onboarding, where a new sync starts only when they ask for it

### Requirement: Delete account
A signed-in user SHALL be able to delete their ContribFinder account (`DELETE /api/v1/auth/account`, CSRF-protected). The system SHALL cancel the user's jobs, ask GitHub to revoke the authorization when connected, delete the stored credential and all GitHub-derived data as above, delete the user, and end the session. A failed revocation SHALL NOT stop the deletion and SHALL be recorded. After deletion, signing in with the same GitHub account SHALL create a new, empty account.

#### Scenario: Account deleted
- **WHEN** a user deletes their account
- **THEN** the user, their credential and their data no longer exist, the session is ended, and later requests with the old cookie are unauthenticated

#### Scenario: Revocation fails
- **WHEN** GitHub revocation fails during account deletion
- **THEN** the account and data are still deleted and the failure is recorded without the token

### Requirement: Audit of data deletion
The system SHALL record an audit entry for every GitHub data deletion and account deletion, with the action, the outcome, the time and counts of what was deleted, and never any credential or deleted content. Audit entries SHALL be kept when the account is deleted, with the user reference removed.

#### Scenario: Account deletion audited
- **WHEN** a user deletes their account
- **THEN** an `account_deleted` audit entry exists afterwards, with no user reference and no credential

### Requirement: Privacy information and data controls in the interface
The system SHALL provide a public privacy page that lists what ContribFinder stores (GitHub account identifier and username, profile information, profile README, public repository metadata and README content, public contribution information, the derived developer profile, recommendations, saved and dismissed projects, feedback events, audit entries), why, how long it is kept (until the user deletes it or the account; audit entries without user reference), and how to delete it. The signed-in dashboard SHALL offer "Delete GitHub data" and "Delete account", each behind a confirmation that says what will be deleted, and SHALL link to the privacy page.

#### Scenario: Privacy page without signing in
- **WHEN** a visitor opens `/privacy`
- **THEN** the page lists each stored data category, its purpose, its retention and how to delete it

#### Scenario: Confirmation required
- **WHEN** the user clicks "Delete account"
- **THEN** nothing is deleted until they confirm in a dialog that describes what will be deleted
