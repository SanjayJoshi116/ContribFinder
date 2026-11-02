## MODIFIED Requirements

### Requirement: Retry policy
The SPA SHALL retry a failed data request only when it failed without a response (network
error) or with a 5xx status, at most twice. A 4xx response SHALL NOT be retried; its result SHALL
be shown as soon as it arrives. A successful response whose body cannot be read SHALL NOT be
retried. Mutations SHALL NOT be retried. Automated tests SHALL use the same retry rules as
production.

#### Scenario: Profile not analyzed yet
- **WHEN** `GET /api/v1/profile` answers `404 not_analyzed`
- **THEN** one request is made and the page shows the profile-being-prepared message without waiting

#### Scenario: Server error
- **WHEN** a request fails with 503 and then succeeds
- **THEN** the data is shown after the retry

#### Scenario: Throttled
- **WHEN** a request answers 429
- **THEN** it is not retried

#### Scenario: Unreadable success body
- **WHEN** a data request answers 200 with a body that is not JSON (for example an HTML page)
- **THEN** it is not retried and fails with code `invalid_response`

## ADDED Requirements

### Requirement: Request failures
Every failed API call made by the SPA SHALL report an HTTP status (0 when no response arrived)
and a machine-readable code: the server's error code when the response carries the error
envelope, `http_error` when it does not, `network_error` when no response arrived, and
`invalid_response` when a successful response's body cannot be read. A `Retry-After` header in
seconds SHALL be reported with the failure whether or not the body carries the envelope. A
state-changing call that cannot obtain a CSRF token SHALL report the token request's own status
and code. Concurrent state-changing calls SHALL share one CSRF token request.

#### Scenario: Offline
- **WHEN** a request fails before any response arrives
- **THEN** it fails with status 0 and code `network_error`

#### Scenario: Throttled CSRF token request
- **WHEN** a save is made without a CSRF cookie and `GET /api/v1/auth/csrf/` answers 429 with the error envelope
- **THEN** the save fails with status 429 and the envelope's code, and the save request is not sent

#### Scenario: Concurrent mutations without a CSRF cookie
- **WHEN** two state-changing calls start while no CSRF cookie is set
- **THEN** one `GET /api/v1/auth/csrf/` is sent and both calls use its token

#### Scenario: Wait without an envelope
- **WHEN** a request answers 503 with a plain-text body and `Retry-After: 30`
- **THEN** it fails with code `http_error` and a wait of 30 seconds
