## MODIFIED Requirements

### Requirement: Disconnect GitHub
The system SHALL let a signed-in user disconnect GitHub. Disconnect SHALL delete the stored token and GitHub account link at once, delete the user's GitHub-derived data (as defined by GitHub data deletion), keep only the account and its audit trail, and end every session of the user, on every device. It SHALL ask GitHub to revoke the app's authorization in the background, never inside the request; the background revocation SHALL hold the token only encrypted, SHALL be retried on temporary failures and on rate limits (waiting at most the configured maximum retry delay before each retry, however long a wait GitHub asks for), and a final failure SHALL be recorded without the token. The response SHALL say whether a revocation was queued or the user had no GitHub connection.

#### Scenario: Successful disconnect
- **WHEN** a signed-in user sends `POST /api/v1/auth/github/disconnect` with a valid CSRF token
- **THEN** the system deletes the stored token, the GitHub account link and the user's GitHub-derived data, queues the revocation of the authorization, invalidates the session and responds with success and the revocation `queued`

#### Scenario: Other sessions end too
- **WHEN** a user signed in on two devices disconnects GitHub from one of them
- **THEN** later requests from the other device's session are unauthenticated

#### Scenario: GitHub revocation fails
- **WHEN** the background revocation request to GitHub keeps failing or timing out
- **THEN** the local token, GitHub account link and GitHub-derived data are deleted already, the session ended already, and the revocation failure is recorded without the token

#### Scenario: GitHub is slow
- **WHEN** GitHub does not answer while a user disconnects
- **THEN** the disconnect request completes without waiting for GitHub

#### Scenario: Sign in again after disconnect
- **WHEN** a user who disconnected signs in with the same GitHub account again
- **THEN** a GitHub account link is re-created for their existing user, and their data is synced from scratch

#### Scenario: Revocation rate-limited with a long wait
- **WHEN** GitHub answers the background revocation with a rate limit whose reset is an hour away
- **THEN** the revocation is retried after at most the maximum retry delay instead of being recorded as failed
