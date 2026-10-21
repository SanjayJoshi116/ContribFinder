## Context

See proposal.md for motivation. This change covers rows A-2, A-3, A-4, A-5, A-6, A-11, A-13,
A-14, B-13, C-1, C-6, C-9 and H-1 in `Bug_Backlog.md`, all verified. The verification notes
narrow A-4 and A-11 and widen B-13 (one manifest fails discovery for every user). They also add
an H-1 extra: `cached_db` sessions hit Redis too.

Current state that shapes the approach:
- **`_error_for` (`services/github/client.py`).** A 403 or 429 is a rate limit only with
  `Retry-After`, with `X-RateLimit-Remaining: 0`, or when it is a 429. Every other 403 is
  `GitHubForbidden`. The body is never read.
- **Errors that some callers absorb as data or skip.** `count_contributors` turns
  `GitHubForbidden` into `None` ("too large to list"). Sync's `SKIPPABLE` holds
  `GitHubNotFound`, `GitHubForbidden` and `GitHubClientError`. Analysis's `PERMANENT_ERRORS`
  holds 404, 451 and `GitHubForbidden`. A secondary limit misread as forbidden is therefore
  dropped, skipped or made permanent.
- **No redirects.** `httpx.Client` doesn't follow redirects (the default), so `_get` sends a
  301 or 307 to `_error_for`, which returns a plain `GitHubClientError`. `get_repository`
  already returns GitHub's current `full_name`; the "follows renames" comment in analysis
  assumes the redirect was followed.
- **Sync steps.**
  - `_step_languages` catches only `GitHubNotFound`.
  - `_step_readme` goes through `get_profile_readme`, which absorbs only 404.
  - `_step_topics` inserts `RepositoryTopic` rows for the pks in `job.metadata["repo_topics"]`
    without checking that those rows still exist.
  - `_store_profile` writes `GitHubProfile` only.
- **Decryption.** `GitHubClient.for_user` calls `decrypt_token`, which raises
  `TokenDecryptionError(Exception)`. `decide_retry` maps that to `internal_error`.
- **Sign-in identity.** `fetch_identity` calls `response.json()` and `data["id"]` unguarded.
  The callback catches only `OAuthError`, and `_auth_error` audits and redirects.
- **Manifests.** `parse_manifest` catches `ValueError`, `TypeError`, `AttributeError` and
  `TOMLDecodeError`. `json.loads` on deep nesting raises `RecursionError`.
- **Repository analysis.** `RepositoryAnalysisService.run` catches `PERMANENT_ERRORS` from
  `_fetch` and calls `lifecycle.fail`. Everything else calls `lifecycle.release` and re-raises.
  Discovery's `_analyze` hands any exception to the job thread, which fails the job.
- **Background refresh.** `_refresh` (`repositories/tasks.py`) logs a non-retryable decision
  and returns. The repository is already released to its previous state (STALE, DISCOVERED or
  FAILED). The backlog picks STALE and due DISCOVERED repositories on every beat, ordered by
  `lifecycle_changed_at`, so the same repository is queued again each time.
- **Redis on the request path.**
  - Throttles: DRF's default throttle classes use the `default` cache, which is `RedisCache`
    when `REDIS_URL` is set, with a 5 s socket timeout.
  - Sessions: `SESSION_ENGINE = cached_db`. In Django 5.2, `load()` guards the cache get but
    not the cache set it does after a database hit, and `save()` writes the cache too.
  - Health (`core/api.py`) already has `throttle_classes = []`.

## Goals / Non-Goals

**Goals:**
- Each GitHub response maps to the right error class at one place (`_error_for` and
  `_get`). Callers keep their existing `except` clauses and become correct.
- Within a job, an error tied to one repository or manifest affects only that repository or
  manifest. An error tied to the job (rate limit, outage, credentials, cancellation, database)
  still goes through the job's retry policy.
- No API or OpenAPI change, and no change to step names or job types.

**Non-Goals:**
- Making workers tolerate a Redis outage. The broker is Redis, and the ETag cache is A-16
  (batch 11).
- A general circuit breaker for the cache. Only the throttle path gets a backoff.
- Re-checking eligibility on stored data (batch 7). Stale recommendations stay as they are
  (batch 6).

## Decisions

### D1. Secondary rate limits are detected from the error message (A-2, C-6)
In `_error_for`, a 403 that has neither `Retry-After` nor `Remaining: 0` is checked further.
The checker reads the JSON body's `message`, or the raw text when the body isn't JSON, and
looks at the first 1 KB at most, lower-cased. If that text contains `secondary rate limit` or
`abuse detection`, the response becomes
`GitHubRateLimited(where, SECONDARY_LIMIT_DEFAULT_WAIT)` (60 s, GitHub's documented minimum).
Otherwise it stays `GitHubForbidden`. The message never goes into the exception text: errors
carry only the status and path.

All of A-2's paths then become rate limits:
- `count_contributors` no longer returns `None` for one.
- Sync never skips one.
- Analysis releases the repository instead of failing it.

C-6 is fixed with no change to `PERMANENT_ERRORS`: a genuine 403 (for example "Repository
access blocked") stays permanent.

**Alternative:** treat every 403 with no `Retry-After` as rate limited when
`X-RateLimit-Remaining` is low. That is a heuristic GitHub doesn't document. The message is
what GitHub tells clients to check.

### D2. Redirects are followed on the API host only (A-4, C-1)
`_get` loops up to `MAX_REDIRECTS = 3` hops on 301, 302, 307 and 308:
- It resolves `Location` against the request URL.
- It requires the result to be on the `GITHUB_API_BASE_URL` host. Otherwise it raises
  `GitHubClientError` (D-style message: "Redirect points outside the GitHub API host"), as
  `_next_link` already does for pagination.
- It re-issues the GET with the same `Accept` and `Authorization` headers.
- Past the hop limit, it raises `GitHubClientError`.

The ETag cache key stays the original URL, so a later request for the old name still sends
`If-None-Match`. GitHub's rename redirect points to `/repositories/{id}`, which serves the same
payload with the current `full_name`. `_record_rate_limit` runs for every hop.

`httpx` `follow_redirects=True` isn't used. It would strip `Authorization` when the origin
changes (safe), but it would follow redirects to other hosts without the token. That turns an
off-host redirect into an unauthenticated request instead of an error. It also hides the hop
count from the cache logic.

Pagination `Link` URLs are absolute and already host-checked. A redirect inside pagination
goes through the same loop.

### D3. An undecryptable token is an auth error (A-6)
`GitHubClient.for_user` catches `TokenDecryptionError` and raises
`GitHubAuthError("Stored GitHub token cannot be decrypted")` from `None`. `decide_retry` then
returns `Fail("github_auth_invalid")`, which the frontend already shows as "sign in again".

`TokenDecryptionError` stays outside the `GitHubError` hierarchy: `services/crypto.py` must not
depend on `services/github`. Other callers of `decrypt_token` (revocation on disconnect, and
`revoke_replaced_token`) keep their current handling.

### D4. Sync degrades per repository (A-3, A-5, A-11, A-13)
- **Languages.**
  - `_step_languages` catches `GitHubNotFound` first and records `{}` (as today).
  - It then catches `SKIPPABLE` (forbidden, other 4xx including 451): it writes nothing, so the
    previous languages stay, and appends the pk to the metadata list `languages_skipped`.
  - Both cases add the pk to `languages_done`, so a retried job doesn't fetch the repository
    again.
  - Rate-limit and transient errors are not in `SKIPPABLE`, so they still propagate.
- **Profile README.**
  - `get_profile_readme` keeps absorbing only 404.
  - `_step_readme` catches `SKIPPABLE` around the fetch and returns `Step.SKIPPED`, writing
    nothing. The analysis reads the stored README, so the previous one stays in use.
  - `SKIPPED` is already in `FINISHED`, so a retried job doesn't repeat the step.
- **Topics.** `_step_topics` reads the existing pks once:
  `set(Repository.objects.filter(pk__in=...).values_list("pk", flat=True))`, inside
  `job_write`. It writes only for those pks. The deleted-row case is a rename race (A-11
  partial), and the next sync re-plans it.
- **Account identity.** `_store_profile` also runs
  `GitHubAccount.objects.filter(user=self.user).update(username=gh.login, avatar_url=gh.avatar_url)`,
  inside the same `job_write`. It's a filter-update, so a disconnect that deleted the account
  meanwhile updates nothing.

### D5. Malformed identity is an OAuth error (A-14)
`fetch_identity` wraps `response.json()` and the field reads (`int(data["id"])`,
`str(data["login"])`). It catches `ValueError`, `TypeError` and `KeyError` and raises
`OAuthError("identity_failed", "GET /user returned an unexpected body")`. It also checks that
the payload is a dict and that `login` isn't empty. The callback's existing `except OAuthError`
audits the failure and redirects with `auth_error=failed`.

### D6. Manifest parsing never raises (B-13)
`parse_manifest` adds `RecursionError` to the caught tuple, and the debug log stays.

`MemoryError` isn't caught:
- Manifests over `GITHUB_MANIFEST_MAX_BYTES` are skipped before parsing, so a manifest can't
  exhaust memory by size.
- A real `MemoryError` belongs to the process, not to one manifest.

The parsers stay pure functions, and the change is one line plus tests for each JSON- and
TOML-based parser (`package.json`, `pyproject.toml`, `Cargo.toml`).

### D7. Repository analysis keeps repository-specific errors to the repository (C-1)
`RepositoryAnalysisService.run` sorts what `_fetch` raises into three groups, checked in this
order:

1. **Propagate** (release the claim, re-raise; unchanged):
   - `GitHubRateLimited`, `GitHubTransientError`, `GitHubAuthError`;
   - `JobCancelled`, `ClaimLost`;
   - `DatabaseError`;
   - any `BaseException` that isn't an `Exception`.
2. **Permanent for the repository** (`lifecycle.fail`, `Outcome.FAILED`): the existing
   `PERMANENT_ERRORS` and codes, plus `GitHubClientError` → `client_error`. It is checked
   after its subclasses, so `GitHubUnavailableForLegalReasons` keeps `unavailable`.
3. **Response that can't be interpreted** (`lifecycle.fail` with `invalid_response`): `KeyError`,
   `ValueError`, `TypeError` and `IndexError` raised by `_fetch`. They come from `from_api`
   parsing and other response handling. `_fetch` writes nothing to the database except the
   claim renewal, so these can't be infrastructure errors. The log line carries the repository
   and the exception type only.

`_store` (the write transaction) is left unchanged: errors there still release and propagate,
because they are database or code errors, not repository data.

`ERROR_CODES` becomes an ordered tuple of `(class, code)` pairs, and the most specific class
wins. The comment "follows renames" becomes true with D2.

`lifecycle.fail` already sets `is_eligible=False` with `REPOSITORY_UNAVAILABLE`, and the
existing FAILED retry (`REPO_FAILED_RETRY_HOURS`) re-checks the repository later. A
`client_error` or `invalid_response` caused by a GitHub-side glitch therefore heals within a
day, which is the same contract as `not_found`.

**Alternative:** catch every `Exception` from `_fetch` as `invalid_response`. That would also
swallow programming errors such as `AttributeError` from a refactor. The narrow list keeps
real bugs loud.

### D8. A refresh failure without a retry is recorded (C-9)
- **Data.** New field `Repository.refresh_failed_at = DateTimeField(null=True, blank=True)`.
- **`lifecycle.record_refresh_failure(repo_id, code)`.**
  - It runs one UPDATE on the repository pk, excluding `IN_PROGRESS` states and `FAILED`.
  - It sets `lifecycle_error=code` and `refresh_failed_at=now`.
  - It doesn't touch `lifecycle`, `lifecycle_changed_at`, eligibility or `stale_parts`. Stale
    is not gone, so users keep the stored data.
  - It runs after the analysis released its claim. A repository that another worker has
    claimed meanwhile is skipped.
- **`_refresh`.** On `Fail(code)` it calls `record_refresh_failure(repo_id, decision.code)`
  and keeps the warning log. A `GitHubAuthError` from the app credentials is a deployment
  problem, not a repository problem, so it keeps logging only.
- **`lifecycle.complete`.** It clears `refresh_failed_at` (and already clears
  `lifecycle_error`). `fail` also clears `refresh_failed_at`, because the FAILED retry delay
  takes over.
- **Backlog.** `process_repository_backlog` excludes rows with
  `refresh_failed_at >= now - REPO_REFRESH_RETRY_MINUTES` before it orders and slices the
  batch. FAILED rows keep their own delay (`lifecycle_changed_at`).
  - New setting `REPO_REFRESH_RETRY_MINUTES = env.int(..., default=60)`.
  - It is added to the positive-integer list of `core.E020` in `core/checks.py`.

**Alternative:** mark the repository FAILED. That would make it ineligible for every user over
a rate limit or a GitHub outage, which is the bug C-6 describes. **Alternative:** reuse
`lifecycle_changed_at` as the delay clock. That would restart the freshness signal and the
DISCOVERED grace period that batch 4 just separated from claims.

### D9. The request path never needs Redis (H-1)
- **Sessions.** `SESSION_ENGINE = "django.contrib.sessions.backends.db"`. `cached_db` already
  writes every session to the `django_session` table, so existing sessions stay valid. The
  cached copies under `django.contrib.sessions.cached_db*` expire unread. A session read costs
  one indexed primary-key query, which is small next to the queries each API view makes.
- **Throttles.** New `core/throttling.py` with `FailOpenMixin` and subclasses
  `AnonRateThrottle`, `UserRateThrottle` and `ScopedRateThrottle` (same names, so the scopes
  and rates are unchanged).
  - `allow_request` returns `True` without touching the cache while a module-level
    `_cache_down_until` (monotonic time) lies in the future.
  - Otherwise it calls `super().allow_request`, catching `Exception` from the cache call only.
    The mixin wraps `self.cache` in a small proxy whose `get` and `set` re-raise as
    `_CacheUnavailable`, so a bug in a throttle isn't swallowed.
  - On a cache failure it sets `_cache_down_until = now + THROTTLE_CACHE_BACKOFF_SECONDS`,
    logs one warning (exception type only, no request data) and allows the request.
  - `DEFAULT_THROTTLE_CLASSES` points to the three `core.throttling` classes. No view sets
    `throttle_classes` except health (`[]`); the auth views set only `throttle_scope`, so they
    pick up the new classes through the default.
  - New setting `THROTTLE_CACHE_BACKOFF_SECONDS = env.int(..., default=30)`, which is
    checked as a positive integer next to it (`core.E020`).
- **Health** keeps its throttle exemption and its Redis ping. Reporting Redis as down is its
  job.

Failing open trades throttling for availability during an outage. The trade is acceptable:
- Sign-in is still protected by OAuth state (one per issued state, `OAUTH_STATE_MAX_PENDING`).
- The sync cooldown is stored in PostgreSQL.

**Alternative:** fall back to a LocMem throttle cache. That gives per-process limits, which
is close to failing open but more code, and limits that silently differ per worker are
misleading. **Alternative:** lower `REDIS_SOCKET_TIMEOUT`. That would also shorten worker
timeouts and not remove the dependency.

## Risks / Trade-offs

- **The secondary-limit message could change.** If GitHub rewords it, D1 falls back to today's
  behavior (forbidden). Tests pin the current wording ("You have exceeded a secondary rate
  limit") and the older one ("abuse detection mechanism").
- **Redirect loops.** These are bounded by `MAX_REDIRECTS`. A 304 after a redirect is served
  from the original URL's cache entry, which is correct, because the content is the same
  resource.
- **`invalid_response` makes a repository ineligible for a day.** A transient malformed
  payload, if GitHub ever sends one, costs at most `REPO_FAILED_RETRY_HOURS` for that
  repository, instead of failing every user's discovery.
- **Fail-open throttles.** During a Redis outage, clients aren't throttled. The warning log
  makes that visible, and health reports Redis as down.
- **Session reads hit PostgreSQL on every request.** This is an indexed point query. If it ever
  matters, `cached_db` could come back with a guarded cache wrapper.

## Migration Plan

1. Add the `repositories` migration for `refresh_failed_at` (nullable, no backfill).
2. Deploy. Existing sessions keep working (they are in the database). Rollback means
   reverting the code and dropping the column, both safe.
3. Run no data fix. Repositories stuck in the requeue loop today have no
   `refresh_failed_at`, so they are queued once more. If that refresh fails again, the new
   delay applies.

## Open Questions

None.
