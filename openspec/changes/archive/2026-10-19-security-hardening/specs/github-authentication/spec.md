## MODIFIED Requirements

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
