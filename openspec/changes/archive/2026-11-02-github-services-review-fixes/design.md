## Context

See proposal.md (Why) and `Bug_Backlog.md` batch 32. Every bulk lock on shared `Repository` rows
is taken in GitHub ID order (discovery search, `lifecycle.recheck_eligibility`,
`data_deletion._delete_orphans` since 0.12.44). `upsert_repository` locks the row
(`update_or_create`). The repository analysis replaces languages and dependencies while holding the
row lock; the sync's languages and dependencies steps do not. The contributions step stores
`contrib_done: {full_name: pk | None}` in job metadata, None meaning "not stored".

## Goals / Non-Goals

**Goals:** close GHS-1…GHS-10, each with a test, without a migration or API change.

**Non-Goals:** changing which owned repositories are selected (push time, cap); caching policy
beyond a size cap; a shared HTTP layer for `oauth.py` and `GitHubClient` (the revocation only
borrows the rate-limit mapping).

## Decisions

**D1 — Lock order.** `_step_repositories` keeps choosing by push time, then upserts the selection
sorted by `github_id` (GHS-1). `replace_languages` and `replace_dependencies` take the row lock
themselves (`Repository.objects.select_for_update().filter(pk=...)`), so every caller holds it;
the sync calls them inside `job_write` as before (GHS-2). Alternative: lock in the steps only —
rejected, the helpers are shared and the analysis already holds the lock (re-locking a held row is
free).

**D2 — One origin check, one Link parser.** `_api_origin(url)` compares (scheme, host, port) with
`GITHUB_API_BASE_URL`; `_send` (redirects) and the new `_link(header, rel)` (pagination) both use
it. `_next_link` and `_count_from_single_item_page` read `_link(header, "next")` and
`_link(header, "last")`; a next link outside the origin raises `GitHubClientError` (GHS-3, GHS-10).

**D3 — Revocation rate limits.** `oauth._revoke` passes a 403 or 429 response to the client's
`_error_for`; a `GitHubRateLimited` result is raised (the task's `decide_retry` retries it with its
wait), anything else stays `OAuthError("revocation_failed")` (GHS-4).

**D4 — Contributions.** Plan items are merged by the stored pk: prs and pushes summed, `last` the
latest (GHS-5). A name whose fetch hit a `SKIPPABLE` error is recorded in
`contrib_skipped: [full_name]`; the final delete keeps links whose repository's `full_name`
matches a skipped name case-insensitively, with their counts unchanged. Gone (404) or now-owned
repositories still drop their link (GHS-6).

**D5 — Client robustness.** `_send` catches `httpx.HTTPError` (not only `TransportError`):
`DecodingError` and other transport-level errors become `GitHubTransientError`; `httpx.InvalidURL`
(and a Link URL that cannot be parsed) becomes `GitHubClientError` (GHS-7). As built: httpx parses
a redirect's Location itself and raises `RemoteProtocolError` for a malformed one, so that case is
transient (retried, then `github_unavailable`); the test covers a malformed Link URL instead.

**D6 — Cache size cap.** `GITHUB_ETAG_MAX_BYTES` (default 256 KiB, `core.E020` positive integer):
a 200 body longer than it is returned but not cached; an entry cached before stays usable (GHS-8).

**D7 — Frozen dependencies set.** The first attempt stores `dependencies_ids` (the capped,
ordered pks) in metadata; a retry reads that list instead of re-ordering by live `pushed_at`
(GHS-9).

**D8 — Duplicates.** `sync` imports `client._dt` as its date parser; `oauth` imports
`client.API_VERSION` (GHS-10).

## Risks / Trade-offs

- [Lock taken inside `replace_*` for callers that already hold it] → a no-op in PostgreSQL within
  the same transaction.
- [A skipped repository renamed meanwhile keeps a link under its old name] → it is dropped on
  the next sync that reads it.
- [Large READMEs are fetched unconditionally every time] → the cap only skips bodies above
  256 KiB; normal READMEs stay cached.
