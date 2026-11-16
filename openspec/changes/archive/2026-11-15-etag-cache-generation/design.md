## Context

- User-scope ETag keys are `github:etag:{pk}:{sha256}` (`GitHubClient._cache_key`); public ones
  `github:etag:public:...`.
- `delete_github_data` cancels jobs, deletes rows in one transaction, and on commit purges
  `github:etag:{pk}:*` and queues `github.purge_user_cache` with a countdown.
- A worker's request already sent when the purge runs can still `cache.set` afterwards.

## Goals / Non-Goals

**Goals:** no user-scope entry written by work that started before a deletion survives the
deletion, with no timing assumption.

**Non-Goals:** public-scope entries (shared, not personal); crypto-shredding cache bodies.

## Decisions

### D1. Generation in PostgreSQL, write then verify

The generation lives on `User` (system of record; a cache-held counter could be evicted and reset).
The deletion bumps it with `F() + 1` in its transaction; the purge still runs on commit.

The client writes the entry, then reads the generation. Two orders are possible:
- the write lands before the purge's scan: the purge deletes it;
- the write lands after the scan, so after the commit: the read sees the new generation (or no
  user, after account deletion) and the client deletes the entry.

Either way no entry survives. Checking before the write instead would leave a gap between check
and write.

Alternative rejected: putting the generation in the key. A stale worker's entry would be
unreachable but still stored for the TTL, which is what SVC-6 is about.

### D2. Captured at construction, fresh from the database

`for_user` reads `access_token_encrypted` and `user__github_cache_generation` in one query, not
from the passed `User` object, which may be older than a deletion. A client built after the
deletion carries the new generation: its writes are new data the user asked for.

Only clients whose scope is the user's own pk verify; `PUBLIC_SCOPE` clients and `for_app` do not.

### D3. Failures

A failed verify read or delete is logged by type and not raised (as the purge): the entry then
expires within `GITHUB_ETAG_TTL`. The cache backoff (`_cached`) applies to the delete.

### D4. Second purge retired

`_purge_later` is removed. The task `github.purge_user_cache` stays registered for queued messages
(as `revoke_replaced_token`); remove it in a later release.
