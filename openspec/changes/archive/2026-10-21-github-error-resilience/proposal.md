## Why

The app misreads some GitHub responses. Because of that, one repository can fail a whole job,
and a Redis outage can break reads that should only need PostgreSQL. Batch 5 of
`Bug_Backlog.md` (verified) found these gaps. They break two invariants: failures are recorded
as state, never as empty data, and one bad input degrades gracefully.
- **Status mapping.**
  - A secondary-rate-limit 403 with no `Retry-After` and requests still remaining is read as
    "forbidden", not as a rate limit. Contributor counts become "unknown" and skippable steps
    drop data. Shared repositories are marked FAILED and ineligible for every user for 24 hours
    (A-2, C-6).
  - A 301 for a renamed repository is not followed. Contribution evidence for it is dropped,
    and the whole discovery job fails (A-4, C-1).
- **One repository fails a sync.**
  - A 403 or 451 on the languages of one owned repository fails every sync permanently (A-3).
  - So does a 403 or 451 on the profile README repository (A-5).
  - A repository row deleted between the metadata and topics steps also fails the sync (A-11).
- **One manifest or response fails discovery.**
  - A deeply nested `package.json` raises `RecursionError`. Repository analysis re-raises any
    exception, so every discovery run that touches that repository fails, for every user
    (B-13).
  - An unexpected 4xx does the same (C-1).
- **Failures not recorded.** A refresh that fails without a retry is only logged. The
  repository goes back to its previous state with no error, and the backlog requeues it on
  every beat forever (C-9).
- **Auth errors misclassified.**
  - After a key rotation drops an old encryption key, syncs fail as `internal_error` instead of
    `github_auth_invalid`, so the user is never asked to sign in again (A-6).
  - A malformed 200 from `GET /user` during sign-in gives a JSON 500 instead of an
    `auth_error=failed` redirect plus an audit entry (A-14).
- **Stale identity.** A sync refreshes the GitHub profile but not the account's username and
  avatar, which `/auth/me` serves. After a GitHub rename, the old login shows until the next
  sign-in (A-13).
- **Redis as a hidden dependency.** DRF throttles and `cached_db` sessions call Redis on every
  request. With Redis down, every API request returns 500 after the socket timeout (H-1).

Theme 4 of the backlog ("GitHub status mapping") and theme 10 ("Redis as hidden hard
dependency") land together here. Batch 4 shipped the claim and lifecycle helpers this batch
builds on.

## What Changes

- **GitHub client status mapping**
  - A 403 or 429 whose body says a secondary rate limit (or the older abuse-detection message)
    was hit becomes `GitHubRateLimited`, with GitHub's default wait.
  - Redirects (301, 302, 307, 308) are followed up to a small hop limit, but only to the API
    host, with the same credentials. A redirect anywhere else is a client error.
- **Token decryption failure is an auth failure.** `GitHubClient.for_user` turns a token that
  can't be decrypted into `GitHubAuthError`, so jobs fail with `github_auth_invalid`.
- **Sync degrades per repository**
  - Languages: a 403, 451 or other non-retryable 4xx skips that repository and keeps its
    previous languages. The skipped repositories are recorded in job metadata.
  - Profile README: a 403 or 451 records the step as `skipped` and keeps the stored README.
  - Topics: written only for repositories that still exist.
  - Profile step: also updates `GitHubAccount.username` and `avatar_url`.
- **Sign-in identity:** a non-JSON or incomplete `GET /user` response is an `identity_failed`
  OAuth error. It redirects with `auth_error=failed` and is audited.
- **Manifest parsing never raises.** `RecursionError` is caught with the other parse errors,
  so a deeply nested manifest yields no dependencies.
- **Repository analysis isolates repository-specific errors.** A repository moves to FAILED
  with its own error code, and the discovery job continues, when the analysis hits:
  - a non-retryable GitHub 4xx (`client_error`);
  - a response it can't interpret (`invalid_response`).
  Rate limits, transient errors, auth errors, cancellation, lost claims and database errors
  still release the claim and propagate. A `GitHubForbidden` is still permanent, but a
  secondary limit is no longer classified as one.
- **Refresh failures are state.** A background refresh that fails without a retry records the
  error code and the time on the repository and keeps the repository's state. The backlog
  skips that repository until a configured delay has passed.
- **Redis outage tolerance**
  - Throttles fail open: a cache error allows the request and logs a warning. A short
    per-process backoff stops every request from waiting on the socket timeout.
  - Sessions move from `cached_db` to `db`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-data-sync`:
  - Profile ingestion also refreshes the account's username and avatar.
  - Languages and the profile README degrade per repository.
  - Topics skip repositories that no longer exist.
  - Secondary limits without `Retry-After` count as rate limits.
  - Renamed repositories are followed.
  - Malformed manifests never fail a step.
  - An undecryptable stored token fails as `github_auth_invalid`.
- `repository-analysis`:
  - Repository-specific client errors and responses that can't be interpreted are recorded
    as FAILED.
  - A refresh failure without a retry is recorded on the repository and delays the next
    attempt.
- `github-authentication`: a malformed identity response fails sign-in through the normal
  error redirect.
- `api-platform`: throttling and sessions keep working when Redis is unavailable.

## Impact

- **Backend:**
  - `services/github/client.py`: `_error_for`, the redirect handling in `_get`, `for_user`.
  - `services/github/sync.py`: the profile, readme, languages and topics steps.
  - `services/github/oauth.py`: `fetch_identity`.
  - `services/profiling/manifests.py`: `parse_manifest`.
  - `services/repositories/analysis.py`: error classes and codes.
  - `services/repositories/lifecycle.py`: new `record_refresh_failure`; `complete` clears it.
  - `repositories/tasks.py`: `_refresh` and the backlog filter.
  - New `core/throttling.py` with fail-open throttle classes.
  - `config/settings/base.py`: throttle classes, `SESSION_ENGINE`, a new setting.
- **Data:** a migration adds `Repository.refresh_failed_at` (nullable). Existing sessions in
  the `django_session` table stay valid; cached copies are no longer read.
- **API:** unchanged. The OpenAPI schema is unchanged.
- **Settings:**
  - New `REPO_REFRESH_RETRY_MINUTES` (default 60): the delay after a refresh failure.
  - New `THROTTLE_CACHE_BACKOFF_SECONDS` (default 30): the per-process wait after a throttle
    cache error.
- **Out of scope:**
  - Stale-but-not-gone recommendation handling (batch 6).
  - Eligibility re-checks on stored data (batch 7).
  - ETag cache behavior when Redis is down in workers (A-16, batch 11).
