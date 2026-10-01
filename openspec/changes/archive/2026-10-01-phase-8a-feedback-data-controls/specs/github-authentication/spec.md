## MODIFIED Requirements

### Requirement: Disconnect GitHub
The system SHALL let a signed-in user disconnect GitHub. Disconnect SHALL ask GitHub to revoke the app's authorization, delete the stored token and GitHub account link, delete the user's GitHub-derived data (as defined by GitHub data deletion), keep only the account and its audit trail, and end the session. If revocation with GitHub fails, the local token, link and data SHALL still be deleted and the failure recorded.

#### Scenario: Successful disconnect
- **WHEN** a signed-in user sends `POST /api/v1/auth/github/disconnect` with a valid CSRF token
- **THEN** the system asks GitHub to revoke the authorization, deletes the stored token, the GitHub account link and the user's GitHub-derived data, invalidates the session and responds with success

#### Scenario: GitHub revocation fails
- **WHEN** the revocation request to GitHub fails or times out during disconnect
- **THEN** the local token, GitHub account link and GitHub-derived data are still deleted, the session is still ended, and the revocation failure is recorded without the token

#### Scenario: Sign in again after disconnect
- **WHEN** a user who disconnected signs in with the same GitHub account again
- **THEN** a GitHub account link is re-created for their existing user, and their data is synced from scratch

### Requirement: Audit trail for sensitive account actions
The system SHALL record an audit entry for every sign-in, sign-in failure, logout, GitHub disconnect, GitHub data deletion and account deletion. Each entry SHALL hold the user (if known and not deleted), the action, the outcome and a timestamp, and SHALL NOT hold any credential.

#### Scenario: Disconnect is audited
- **WHEN** a user disconnects GitHub
- **THEN** an audit entry with action `github_disconnect`, the user, the outcome (including whether revocation succeeded) and a timestamp is stored

#### Scenario: Data deletion is audited
- **WHEN** a user deletes their GitHub data
- **THEN** an audit entry with action `github_data_deleted`, the user, the outcome and a timestamp is stored
