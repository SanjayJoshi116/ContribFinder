# github-authentication Specification

## Purpose

Lets a developer sign in to ContribFinder with their GitHub account, stay signed in through a secure session, sign out, and disconnect GitHub. The GitHub credential stays protected on the server at all times.

## Requirements

### Requirement: Sign in with GitHub
The system SHALL let an unauthenticated user start GitHub authorization. It SHALL redirect them to GitHub with a single-use, unguessable `state` value tied to their browser session. It SHALL request only the minimum permissions needed to read public GitHub data. A browser session SHALL be able to hold several pending `state` values at once, so sign-in started in more than one tab can complete from any of them. Each pending value SHALL expire after a short lifetime, and the number kept per session SHALL be bounded.

#### Scenario: Start authorization
- **WHEN** an unauthenticated user requests `GET /api/v1/auth/github`
- **THEN** the system responds with a redirect to GitHub's authorization page that includes the configured client ID, callback URL and a newly generated `state` value

#### Scenario: Minimum permissions requested
- **WHEN** the authorization redirect is generated
- **THEN** it requests no scopes beyond those needed to read the user's public profile and public repositories

#### Scenario: Sign-in started in two tabs
- **WHEN** the same browser session starts authorization in tab A and then in tab B, and the user completes tab A's authorization first
- **THEN** tab A's callback signs the user in, and tab A's `state` cannot be used again

#### Scenario: Expired pending state
- **WHEN** a callback arrives with a `state` issued to the session longer ago than the pending-state lifetime
- **THEN** the system treats it as a state mismatch and does not contact GitHub's token endpoint

#### Scenario: Bounded pending states
- **WHEN** a session starts authorization more times than the per-session limit without completing any
- **THEN** only the most recent states up to the limit remain valid

### Requirement: Handle the authorization callback
The system SHALL complete sign-in only when the callback's `state` matches the one issued to the same browser session and GitHub successfully exchanges the authorization code. On success it SHALL create the local user and linked GitHub account, or update them if they already exist, keyed by the GitHub user ID. It SHALL then establish an authenticated session and redirect to the frontend. If GitHub's identity response cannot be read (not JSON, missing the user ID, or a login that is missing, empty or not a string), sign-in SHALL fail like any other GitHub error during the callback. When a returning sign-in replaces a stored token with a different one, the system SHALL ask GitHub to revoke the replaced token; a failed revocation SHALL NOT block the sign-in and SHALL be recorded without the token. A deactivated user SHALL NOT be signed in: the system SHALL store nothing, start no sync, ask GitHub to revoke the token it just received, record the refusal in the audit trail and redirect with the `failed` error code. Any unexpected error after the code exchange SHALL end the same way (no session, a recorded failure without any token, the `failed` error code), never a server error page.

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

#### Scenario: Malformed identity response
- **WHEN** the code exchange succeeds but GitHub's `GET /user` answers 200 with a body that is not JSON, or JSON without the user ID or login
- **THEN** the system does not create a session or store the token, records the failure in the audit trail without any token, and redirects to the frontend with the `failed` authentication error code instead of answering with a server error

#### Scenario: Deactivated user
- **WHEN** the callback succeeds for a GitHub user ID whose user has been deactivated
- **THEN** the system creates no session, stores no token, starts no sync, asks GitHub to revoke the token it received, records a sign-in failure without any token, and redirects with the `failed` error code

#### Scenario: Unexpected error while linking
- **WHEN** storing the account or starting the session fails after a successful code exchange
- **THEN** the system creates no session, records a sign-in failure without any token, and redirects with the `failed` error code instead of answering with a server error

### Requirement: GitHub credential protection
The system SHALL store the GitHub access token encrypted at rest. It SHALL NOT include the token, the authorization code or the client secret in any API response, URL, log entry or error report. As a backstop, log output SHALL mask credential values (access and refresh tokens, client secret, authorization code, OAuth `state`, and any `Authorization` header value) whether they appear as query parameters, quoted or unquoted `key=value` pairs, JSON or dictionary entries, or GitHub token strings. Masking SHALL never cause the logging call itself to fail.

#### Scenario: Token is encrypted in storage
- **WHEN** a GitHub account is stored after successful sign-in
- **THEN** the persisted token value is ciphertext that differs from the plaintext token, and the server can decrypt it back to the original

#### Scenario: Token never reaches the client
- **WHEN** any authenticated API endpoint returns user or account data
- **THEN** the response body contains no access token, authorization code or client secret

#### Scenario: Token never logged
- **WHEN** sign-in succeeds or fails and log output is captured
- **THEN** no captured log line contains the access token, authorization code or client secret

#### Scenario: Quoted and structured credential forms
- **WHEN** a log line contains `client_secret='…'`, `access_token="…"`, `{'state': '…'}` or `Authorization: token …` with a value in any format
- **THEN** the captured line shows the key with the value masked

#### Scenario: Malformed log call
- **WHEN** code makes a log call whose arguments do not match its format string
- **THEN** the call returns normally to its caller, and a masked line is still emitted

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
The system SHALL let a signed-in user disconnect GitHub. Disconnect SHALL delete the stored token and GitHub account link at once, delete the user's GitHub-derived data (as defined by GitHub data deletion), keep only the account and its audit trail, and end every session of the user, on every device. It SHALL ask GitHub to revoke the app's authorization in the background, never inside the request; the background revocation SHALL hold the token only encrypted, SHALL be retried on temporary failures, and a final failure SHALL be recorded without the token. The response SHALL say whether a revocation was queued or the user had no GitHub connection.

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

### Requirement: Audit trail for sensitive account actions
The system SHALL record an audit entry for every sign-in, sign-in failure, logout, GitHub disconnect, GitHub data deletion and account deletion. Each entry SHALL hold the user (if known and not deleted), the action, the outcome and a timestamp, and SHALL NOT hold any credential. Audit entries SHALL NOT be added, changed or deleted through the administration interface.

#### Scenario: Disconnect is audited
- **WHEN** a user disconnects GitHub
- **THEN** an audit entry with action `github_disconnect`, the user, the outcome (including whether a revocation was queued) and a timestamp is stored

#### Scenario: Data deletion is audited
- **WHEN** a user deletes their GitHub data
- **THEN** an audit entry with action `github_data_deleted`, the user, the outcome and a timestamp is stored

#### Scenario: Audit entries are read-only for staff
- **WHEN** a staff user opens the audit entries in the administration interface
- **THEN** they can list and view entries but cannot add or delete any
