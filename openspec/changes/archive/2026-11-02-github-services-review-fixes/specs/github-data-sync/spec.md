## MODIFIED Requirements

### Requirement: Credential use during sync
Sync SHALL authenticate to GitHub with the user's stored token. The token SHALL NOT appear in job records, job arguments, error messages or logs. If GitHub rejects the token, the user has no connected GitHub account, or the stored token cannot be decrypted with any configured key, the sync SHALL stop without retrying and report that the user must sign in again. Redirects and pagination links SHALL be followed with the token only to the GitHub API's own origin (same scheme, host and port); a redirect or next-page link anywhere else, including plain HTTP or another port on the same host, SHALL NOT be followed and SHALL NOT receive the token.

#### Scenario: Token revoked on GitHub
- **WHEN** GitHub answers a sync request with 401
- **THEN** the job moves to FAILED with error code `github_auth_invalid` and is not retried

#### Scenario: No secrets in job data
- **WHEN** any sync job runs, succeeds or fails
- **THEN** its stored fields, queued task arguments and log output contain no access token

#### Scenario: Encryption key removed
- **WHEN** the key that encrypted the user's stored token is no longer among the configured keys and a sync runs
- **THEN** the job moves to FAILED with error code `github_auth_invalid`, is not retried, and makes no GitHub request

#### Scenario: Redirect to another host
- **WHEN** GitHub answers a request with a redirect whose location is not on the GitHub API host
- **THEN** the redirect is not followed, no request carrying the token is sent to that host, and the request fails as a client error

#### Scenario: Redirect to plain HTTP
- **WHEN** GitHub answers a request with a redirect to `http://` on the GitHub API host
- **THEN** the redirect is not followed, no request carrying the token is sent over plain HTTP, and the request fails as a client error

#### Scenario: Next-page link to plain HTTP
- **WHEN** GitHub answers a listing with a next-page link to `http://` or another port on the GitHub API host
- **THEN** the link is not followed, no request carrying the token is sent there, and the request fails as a client error

### Requirement: External contribution ingestion
A sync SHALL collect the user's public contributions to repositories they do not own:
- merged pull requests authored by the user, up to a configured number;
- public push activity in the recent public events GitHub provides.

For the contributed repositories with the most contributions, up to a configured number (default 20), the system SHALL store repository metadata, languages and topics as for owned repositories. It SHALL link them to the user as contributor with the number of merged pull requests and pushes observed, and the time of the latest one. Contributor links that are no longer observed SHALL be removed on the next successful sync; a link to a repository that is still observed but cannot be read this time (forbidden, unreadable) SHALL be kept with its previous counts. Contributions observed under two names of one repository (renamed or transferred) SHALL be counted together. Private activity SHALL NOT be requested. If GitHub rejects the contribution search for the user as invalid, the step SHALL be recorded as skipped and the sync SHALL complete. A contributed repository that was renamed or transferred on GitHub SHALL be followed to its current name and stored under it; a repository that cannot be read (not found, forbidden or another non-retryable client error) SHALL be skipped without failing the sync.

#### Scenario: Merged pull requests recorded
- **WHEN** the user has 3 merged pull requests to `pallets/flask` and 1 to `psf/requests`
- **THEN** both repositories are stored with languages and topics, and linked to the user as contributor with 3 and 1 merged pull requests

#### Scenario: Own repositories excluded
- **WHEN** the user has merged pull requests to a repository they own
- **THEN** that repository is not linked as a contributed repository

#### Scenario: Contribution search rejected
- **WHEN** GitHub answers the contribution search with 422
- **THEN** the contributions step is skipped and the sync completes

#### Scenario: Contribution repository cap
- **WHEN** the user contributed to 35 repositories and the cap is 20
- **THEN** only the 20 repositories with the most contributions are stored and linked, and the job metadata records that the cap was applied

#### Scenario: Renamed contributed repository
- **WHEN** the user's merged pull requests point to `old-org/tool`, and GitHub answers requests for it with a 301 redirect to the repository's current API location, `new-org/tool`
- **THEN** the repository is stored as `new-org/tool` with its languages and topics and linked to the user as contributor

#### Scenario: Contributed repository temporarily unreadable
- **WHEN** a repository the user is linked to as contributor is still among their contributions but answers 403 during a sync
- **THEN** the repository is skipped, the sync completes, and the contributor link keeps its previous counts

#### Scenario: Contributions under an old and a new name
- **WHEN** the user has 3 merged pull requests to `old-org/proj` and 2 pushes to `new-org/proj`, which GitHub resolves to the same repository
- **THEN** one contributor link is stored with 3 merged pull requests and 2 pushes
