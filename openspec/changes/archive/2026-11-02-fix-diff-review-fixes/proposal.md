## Why

The fix-diff review of batches 32–34 (`Bug_Backlog.md` batch 35, FD-1…FD-10), run on the
combined 0.12.45–0.12.47 diff after one `/simplify`, found that a rate-limited revocation whose
wait exceeds `GITHUB_MAX_RETRY_DELAY` ends on the first try (GHS-4 made rate limits
`GitHubRateLimited`, and the shared retry policy fails a wait above the cap), so a grant the user
asked to revoke can stay valid on GitHub. It also found the shared status → error mapping naming
`GET` for the revocation's DELETE, and a test helper that shadowed `services.jobs.new_job`. The
fixes were made before commit; this change records them.

## What Changes

- FD-1: `revoke_later` retries a rate limit after `min(wait, GITHUB_MAX_RETRY_DELAY)`, until
  `REVOCATION_ATTEMPTS` run out; the `revoke_grant`/`revoke_token` docstrings name
  `GitHubRateLimited`.
- FD-8: `errors.error_for_response(response, path, method="GET")`; the revocation passes
  `DELETE`.
- FD-10: test helper `running_sync_job(user)` (was `new_job`).
- Not changed: FD-2…FD-7, FD-9 accepted or wontfix (`Bug_Backlog.md` batch 35).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-authentication`: "Disconnect GitHub" (the background revocation is also retried when
  GitHub rate-limits it, however long the wait it asks for).

## Impact

- `apps/backend/github/tasks.py`, `services/github/{errors,oauth}.py`, tests.
- No migration, no API change (OpenAPI `1.0.0`), no frontend change, no ranking change. Ships in
  the same release as the batches it reviews.
