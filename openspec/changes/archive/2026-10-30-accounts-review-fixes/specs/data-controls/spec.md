## MODIFIED Requirements

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
