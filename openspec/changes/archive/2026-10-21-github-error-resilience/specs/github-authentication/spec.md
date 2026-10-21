## MODIFIED Requirements

### Requirement: Handle the authorization callback
The system SHALL complete sign-in only when the callback's `state` matches the one issued to the same browser session and GitHub successfully exchanges the authorization code. On success it SHALL create the local user and linked GitHub account, or update them if they already exist, keyed by the GitHub user ID. It SHALL then establish an authenticated session and redirect to the frontend. If GitHub's identity response cannot be read (not JSON, or missing the user ID or login), sign-in SHALL fail like any other GitHub error during the callback. When a returning sign-in replaces a stored token with a different one, the system SHALL ask GitHub to revoke the replaced token; a failed revocation SHALL NOT block the sign-in and SHALL be recorded without the token.

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
