## Why

SVC-16 (`Bug_Backlog.md`, batch 31): the timed second purge after a GitHub data deletion is a
stopgap. A cancelled sync's in-flight request can write a user-scope ETag entry after the purge at
commit (SVC-6); the second purge, queued `SYNC_STALE_AFTER_SECONDS` later, narrows the window, and a
worker slower than that still escapes it (SVC-15). Until then the entry outlives "delete my data"
for up to `GITHUB_ETAG_TTL`.

## What Changes

- `User.github_cache_generation` (integer, default 0). `delete_github_data` increments it in the
  deletion transaction.
- `GitHubClient.for_user` reads the generation with the token when the client uses the user's own
  cache scope. After each ETag cache write the client re-reads it; if it changed or the user is
  gone, the client deletes the entry it just wrote (write, then verify).
- The timed second purge is no longer queued. The `github.purge_user_cache` task stays for
  messages queued before this release.
- SVC-6 and SVC-15 are fixed at the root; SVC-16 fixed.

## Capabilities

### Modified Capabilities

- `data-controls`: a new scenario under "Delete GitHub-derived data": a response that arrives after
  the deletion committed is not left in the user's cache.

## Impact

- Migration `accounts/0006` (one column with a default).
- One primary-key query per user-scope ETag cache write. Public-scope writes are unchanged.
- No API change.
