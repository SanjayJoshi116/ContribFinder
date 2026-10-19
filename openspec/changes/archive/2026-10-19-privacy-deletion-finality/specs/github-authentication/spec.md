## MODIFIED Requirements

### Requirement: Handle the authorization callback
The system SHALL complete sign-in only when the callback's `state` matches the one issued to the same browser session and GitHub successfully exchanges the authorization code. On success it SHALL create the local user and linked GitHub account, or update them if they already exist, keyed by the GitHub user ID. It SHALL then establish an authenticated session and redirect to the frontend. When a returning sign-in replaces a stored token with a different one, the system SHALL ask GitHub to revoke the replaced token; a failed revocation SHALL NOT block the sign-in and SHALL be recorded without the token.

#### Scenario: First-time sign-in
- **WHEN** GitHub redirects to `GET /api/v1/auth/github/callback` with a valid code and matching state for a GitHub user ID not seen before
- **THEN** the system creates a user and a linked GitHub account (GitHub ID, username, avatar URL), starts a session and redirects to the frontend's signed-in landing route

#### Scenario: Returning user
- **WHEN** the callback succeeds for a GitHub user ID that already has an account
- **THEN** the system updates the stored username, avatar URL and token on the existing account instead of creating a duplicate user

#### Scenario: Replaced token is revoked
- **WHEN** a returning sign-in receives a token different from the stored one
- **THEN** the system stores the new token and asks GitHub to revoke only the old token, leaving the new one valid

#### Scenario: Revoking the replaced token fails
- **WHEN** GitHub cannot be reached while the replaced token is being revoked
- **THEN** the user is still signed in with the new token, and the failure is logged without any token

#### Scenario: State mismatch or missing
- **WHEN** the callback's `state` is missing, already used, or does not match the session
- **THEN** the system does not sign the user in, does not contact GitHub's token endpoint, and redirects to the frontend with an authentication error code

#### Scenario: User denies authorization
- **WHEN** GitHub redirects to the callback with an `error` parameter (for example `access_denied`)
- **THEN** the system does not create a session and redirects to the frontend with an error code indicating that authorization was cancelled

#### Scenario: GitHub token exchange fails
- **WHEN** the code exchange with GitHub fails or times out
- **THEN** the system does not create a session, records the failure without logging the code or any token, and redirects to the frontend with a retryable error code

### Requirement: Disconnect GitHub
The system SHALL let a signed-in user disconnect GitHub. Disconnect SHALL ask GitHub to revoke the app's authorization, delete the stored token and GitHub account link, delete the user's GitHub-derived data (as defined by GitHub data deletion), keep only the account and its audit trail, and end every session of the user, on every device. If revocation with GitHub fails, the local token, link and data SHALL still be deleted and the failure recorded.

#### Scenario: Successful disconnect
- **WHEN** a signed-in user sends `POST /api/v1/auth/github/disconnect` with a valid CSRF token
- **THEN** the system asks GitHub to revoke the authorization, deletes the stored token, the GitHub account link and the user's GitHub-derived data, invalidates the session and responds with success

#### Scenario: Other sessions end too
- **WHEN** a user signed in on two devices disconnects GitHub from one of them
- **THEN** later requests from the other device's session are unauthenticated

#### Scenario: GitHub revocation fails
- **WHEN** the revocation request to GitHub fails or times out during disconnect
- **THEN** the local token, GitHub account link and GitHub-derived data are still deleted, the session is still ended, and the revocation failure is recorded without the token

#### Scenario: Sign in again after disconnect
- **WHEN** a user who disconnected signs in with the same GitHub account again
- **THEN** a GitHub account link is re-created for their existing user, and their data is synced from scratch
