## Context

See proposal.md (Why) and `Bug_Backlog.md` batch 35. `github.revoke_later` asks the shared pure
policy `services/github/retry.decide_retry` what to do after an error. The policy fails a
`GitHubRateLimited` whose `retry_after` exceeds `max_delay` at once: for sync jobs a wait that
long means the job is better failed and started again later. Since GHS-4, `oauth._revoke` raises
`GitHubRateLimited` for a 403/429 rate limit (through `errors.error_for_response`), carrying the
wait to the primary limit's reset, which can be up to an hour.

## Goals / Non-Goals

**Goals:** a rate-limited revocation is retried, never ended by the length of the wait; error
messages name the request's method.

**Non-Goals:** changing `decide_retry` for sync jobs; raising `REVOCATION_ATTEMPTS`; the
accepted rows FD-2…FD-7, FD-9.

## Decisions

**D1 — Cap the wait at the caller.** Before calling `decide_retry`, `revoke_later` replaces a
`GitHubRateLimited` with one whose `retry_after` is `min(retry_after, GITHUB_MAX_RETRY_DELAY)`.
The policy then retries it with its usual 1 s plus jitter, and still fails it once the attempts
run out (`github_rate_limited`). Alternative: a `cap_wait` flag on `decide_retry` — rejected, the
policy stays one rule for every caller and the revocation's need stays in its task.

**D2 — Method in the message.** `error_for_response(response, path, method="GET")`; `_revoke`
passes `"DELETE"`. Messages still carry only method, path and status.

**D3 — Test helper name.** `test_github_sync.running_sync_job(user)` builds the RUNNING sync job
the tests use; it no longer shares a name with `services.jobs.new_job` (a PENDING job).

## Risks / Trade-offs

- [A capped retry can land before the reset and be rate-limited again] → each try uses one
  attempt; four attempts at the cap span about 45 minutes, past the hourly reset in practice.
