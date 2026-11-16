# data-controls Specification

## Purpose

Gives developers control over the data ContribFinder keeps about them: refresh it, see what is stored and why, delete everything derived from GitHub, or delete their account entirely, with each sensitive action audited.
## Requirements
### Requirement: Refresh rebuilds the pipeline
Refreshing (`POST /api/v1/profile/sync`, subject to the existing cooldown) SHALL run the whole pipeline as tracked background jobs: GitHub sync, profile analysis, repository discovery and recommendation generation, each starting when the previous one completes. A failed stage SHALL stop the chain and keep the previous results of later stages. The dashboard SHALL show which stage is running (syncing, analyzing, finding projects, preparing recommendations) and update without a reload.

#### Scenario: Full refresh
- **WHEN** a user refreshes and every stage succeeds
- **THEN** a sync, a discovery and a recommendation generation job complete in that order, and the dashboard shows each stage while it runs

#### Scenario: Discovery fails
- **WHEN** the discovery stage of a refresh fails
- **THEN** no recommendation generation starts from it and the user's previous recommendations are unchanged

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

#### Scenario: Cached response written after deletion
- **WHEN** a sync's GitHub request was in flight while the user deleted their GitHub data, and its response arrives after the deletion committed
- **THEN** the response is not left in the user's GitHub response cache, without waiting for a later purge

#### Scenario: Cache purge fails at deletion
- **WHEN** purging the user's GitHub response cache fails as the deletion commits (a brief cache outage)
- **THEN** the deletion still succeeds, and the purge is tried again in the background until it succeeds or its tries run out; entries left after that expire within the response cache's lifetime

### Requirement: Delete account
A signed-in user SHALL be able to delete their ContribFinder account (`DELETE /api/v1/auth/account`, CSRF-protected). The system SHALL cancel the user's jobs, delete the stored credential and all GitHub-derived data as above, delete the user, and end the session. When connected, it SHALL ask GitHub to revoke the authorization in the background, never inside the request, holding the token only encrypted; a failed revocation SHALL NOT stop the deletion and SHALL be recorded without the token. The deletion audit entry, the anonymization of the user's audit entries and the deletion of the user SHALL happen together or not at all. After deletion, signing in with the same GitHub account SHALL create a new, empty account.

#### Scenario: Account deleted
- **WHEN** a user deletes their account
- **THEN** the user, their credential and their data no longer exist, the session is ended, and later requests with the old cookie are unauthenticated

#### Scenario: Revocation fails
- **WHEN** GitHub revocation fails during account deletion
- **THEN** the account and data are still deleted and the failure is recorded without the token

#### Scenario: Deleting the user fails
- **WHEN** deleting the user row fails after the GitHub data was deleted
- **THEN** no `account_deleted` audit entry exists and the user's earlier audit entries keep their values

### Requirement: Audit of data deletion
The system SHALL record an audit entry for every GitHub data deletion and account deletion, with the action, the outcome, the time and counts of what was deleted, and never any credential or deleted content. Audit entries SHALL be kept when the account is deleted, with the user reference removed. When an account is deleted, its audit entries SHALL also lose every value that identifies the person: GitHub user ID, GitHub username and client address hash. Their action, outcome, time, reason codes and counts SHALL be kept.

#### Scenario: Account deletion audited
- **WHEN** a user deletes their account
- **THEN** an `account_deleted` audit entry exists afterwards, with no user reference and no credential

#### Scenario: Earlier entries anonymized
- **WHEN** a user who signed in several times deletes their account
- **THEN** their earlier sign-in entries still exist with action, outcome and time, but hold no user reference, no GitHub user ID, no GitHub username and no client address hash

### Requirement: Privacy information and data controls in the interface
The system SHALL provide a public privacy page that lists what ContribFinder stores, why, how long it is kept and how to delete it. The list SHALL match what the system actually stores and keeps:
- the GitHub account ID, kept until the account is deleted because it links a returning sign-in to the account;
- the GitHub username, avatar and display name;
- the encrypted GitHub credential;
- profile information and the profile README;
- public repository metadata and README content;
- public contribution information;
- the derived developer profile;
- the candidate pool with the search queries built from the profile;
- recommendations;
- saved and dismissed projects;
- feedback events;
- sync and job history;
- sign-in sessions;
- audit entries, kept after account deletion without any link to the person.

The signed-in dashboard SHALL offer "Delete GitHub data" and "Delete account", each behind a confirmation that says what will be deleted, and SHALL link to the privacy page.

#### Scenario: Privacy page without signing in
- **WHEN** a visitor opens `/privacy`
- **THEN** the page lists each stored data category, its purpose, its retention and how to delete it

#### Scenario: Retention matches behavior
- **WHEN** a visitor reads the retention of the GitHub account identifier and of audit entries
- **THEN** the page says the account ID is kept until account deletion and that audit entries are kept without any identifying value

#### Scenario: Confirmation required
- **WHEN** the user clicks "Delete account"
- **THEN** nothing is deleted until they confirm in a dialog that describes what will be deleted

