## Purpose

Lets a developer sign in to ContribFinder with their GitHub account, stay signed in through a secure session, sign out, and disconnect GitHub. The GitHub credential stays protected on the server at all times.

## ADDED Requirements

### Requirement: Sign in with GitHub
The system SHALL let an unauthenticated user start GitHub authorization. It SHALL redirect them to GitHub with a single-use, unguessable `state` value tied to their browser session. It SHALL request only the minimum permissions needed to read public GitHub data.

#### Scenario: Start authorization
- **WHEN** an unauthenticated user requests `GET /api/v1/auth/github`
- **THEN** the system responds with a redirect to GitHub's authorization page that includes the configured client ID, callback URL and a newly generated `state` value

#### Scenario: Minimum permissions requested
- **WHEN** the authorization redirect is generated
- **THEN** it requests no scopes beyond those needed to read the user's public profile and public repositories

### Requirement: Handle the authorization callback
The system SHALL complete sign-in only when the callback's `state` matches the one issued to the same browser session and GitHub successfully exchanges the authorization code. On success it SHALL create the local user and linked GitHub account, or update them if they already exist, keyed by the GitHub user ID. It SHALL then establish an authenticated session and redirect to the frontend.

#### Scenario: First-time sign-in
- **WHEN** GitHub redirects to `GET /api/v1/auth/github/callback` with a valid code and matching state for a GitHub user ID not seen before
- **THEN** the system creates a user and a linked GitHub account (GitHub ID, username, avatar URL), starts a session and redirects to the frontend's signed-in landing route

#### Scenario: Returning user
- **WHEN** the callback succeeds for a GitHub user ID that already has an account
- **THEN** the system updates the stored username, avatar URL and token on the existing account instead of creating a duplicate user

#### Scenario: State mismatch or missing
- **WHEN** the callback's `state` is missing, already used, or does not match the session
- **THEN** the system does not sign the user in, does not contact GitHub's token endpoint, and redirects to the frontend with an authentication error code

#### Scenario: User denies authorization
- **WHEN** GitHub redirects to the callback with an `error` parameter (for example `access_denied`)
- **THEN** the system does not create a session and redirects to the frontend with an error code indicating that authorization was cancelled

#### Scenario: GitHub token exchange fails
- **WHEN** the code exchange with GitHub fails or times out
- **THEN** the system does not create a session, records the failure without logging the code or any token, and redirects to the frontend with a retryable error code

### Requirement: GitHub credential protection
The system SHALL store the GitHub access token encrypted at rest. It SHALL NOT include the token, the authorization code or the client secret in any API response, URL, log entry or error report.

#### Scenario: Token is encrypted in storage
- **WHEN** a GitHub account is stored after successful sign-in
- **THEN** the persisted token value is ciphertext that differs from the plaintext token, and the server can decrypt it back to the original

#### Scenario: Token never reaches the client
- **WHEN** any authenticated API endpoint returns user or account data
- **THEN** the response body contains no access token, authorization code or client secret

#### Scenario: Token never logged
- **WHEN** sign-in succeeds or fails and log output is captured
- **THEN** no captured log line contains the access token, authorization code or client secret

### Requirement: Authenticated session
The system SHALL keep signed-in state in a server-side session identified by an HTTP-only cookie. Sessions SHALL expire after a configured period. The system SHALL provide an endpoint that returns the current user's identity.

#### Scenario: Current user when signed in
- **WHEN** a signed-in user requests `GET /api/v1/auth/me`
- **THEN** the system returns their user ID, GitHub username, display name, avatar URL and whether GitHub is connected

#### Scenario: Current user when signed out
- **WHEN** a request without a valid session hits `GET /api/v1/auth/me`
- **THEN** the system responds with HTTP 401 in the standard error format

#### Scenario: Session cookie attributes
- **WHEN** a session cookie is issued
- **THEN** it is marked HttpOnly and SameSite=Lax, and in production it is also marked Secure

#### Scenario: Session expiry
- **WHEN** a session is older than the configured maximum age
- **THEN** requests with it are treated as unauthenticated

### Requirement: Logout
The system SHALL let a signed-in user end their session. Logout SHALL keep the GitHub connection and stored data.

#### Scenario: Successful logout
- **WHEN** a signed-in user sends `POST /api/v1/auth/logout` with a valid CSRF token
- **THEN** the session is invalidated, later requests with the old cookie are unauthenticated, and the linked GitHub account is kept

### Requirement: Disconnect GitHub
The system SHALL let a signed-in user disconnect GitHub. Disconnect SHALL ask GitHub to revoke the app's authorization, delete the stored token and GitHub account link, and end the session. If revocation with GitHub fails, the local token and link SHALL still be deleted and the failure recorded.

#### Scenario: Successful disconnect
- **WHEN** a signed-in user sends `POST /api/v1/auth/github/disconnect` with a valid CSRF token
- **THEN** the system asks GitHub to revoke the authorization, deletes the stored token and GitHub account link, invalidates the session and responds with success

#### Scenario: GitHub revocation fails
- **WHEN** the revocation request to GitHub fails or times out during disconnect
- **THEN** the local token and GitHub account link are still deleted, the session is still ended, and the revocation failure is recorded without the token

#### Scenario: Sign in again after disconnect
- **WHEN** a user who disconnected signs in with the same GitHub account again
- **THEN** a GitHub account link is re-created for their existing user

### Requirement: Audit trail for sensitive account actions
The system SHALL record an audit entry for every sign-in, sign-in failure, logout and GitHub disconnect. Each entry SHALL hold the user (if known), the action, the outcome and a timestamp, and SHALL NOT hold any credential.

#### Scenario: Disconnect is audited
- **WHEN** a user disconnects GitHub
- **THEN** an audit entry with action `github_disconnect`, the user, the outcome (including whether revocation succeeded) and a timestamp is stored
