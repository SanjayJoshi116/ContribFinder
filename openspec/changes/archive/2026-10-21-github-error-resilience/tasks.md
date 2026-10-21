## 1. GitHub client status mapping (D1, D2, D3, A-2, A-4, A-6, C-6)

- [x] 1.1 `_error_for`: a 403 or 429 without `Retry-After` or `Remaining: 0` whose JSON `message` (or raw text, first 1 KB, lower-cased) contains `secondary rate limit` or `abuse detection` → `GitHubRateLimited(where, SECONDARY_LIMIT_DEFAULT_WAIT)`; the message never enters the exception text
- [x] 1.2 `_get`: follow 301/302/307/308 up to `MAX_REDIRECTS = 3`, resolving `Location` against the request URL; only on the `GITHUB_API_BASE_URL` host, with the same headers; an off-host location or too many hops → `GitHubClientError`; ETag cache key stays the original URL; `_record_rate_limit` on every hop
- [x] 1.3 `GitHubClient.for_user`: `TokenDecryptionError` → `GitHubAuthError("Stored GitHub token cannot be decrypted")` from None
- [x] 1.4 Tests (`test_github_client.py`, recorded fixtures with respx): secondary-limit 403 with requests remaining and the current and older messages → `GitHubRateLimited` with a wait ≥ 60; a plain 403 ("Repository access blocked") → `GitHubForbidden`; `count_contributors` raises on a secondary limit instead of returning None; 301 to `/repositories/{id}` is followed with the token and returns the current `full_name`; a redirect to another host is not requested (respx asserts no call) and raises `GitHubClientError`; four hops raise; a 304 after a redirect serves the cached body; `for_user` with a token encrypted by a removed key raises `GitHubAuthError`
- [x] 1.5 Test: a sync whose stored token cannot be decrypted ends FAILED `github_auth_invalid` after no GitHub request

## 2. Sync degrades per repository (D4, A-3, A-5, A-11, A-13)

- [x] 2.1 `_step_languages`: `GitHubNotFound` → `{}` as today; `SKIPPABLE` → write nothing, append the pk to metadata `languages_skipped`; both mark the pk done
- [x] 2.2 `_step_readme`: `SKIPPABLE` around `get_profile_readme` → return `Step.SKIPPED` without writing
- [x] 2.3 `_step_topics`: inside `job_write`, write only for pks that still exist
- [x] 2.4 `_store_profile`: also `GitHubAccount.objects.filter(user=...).update(username=gh.login, avatar_url=gh.avatar_url)` in the same `job_write`
- [x] 2.5 Tests (`test_github_sync.py`): a 451 on one repository's languages keeps its earlier languages, lists it in `languages_skipped`, stores the others and completes; a secondary-limit 403 on languages moves the job to RETRYING (with `CELERY_TASK_ALWAYS_EAGER=False`) and skips nothing; a 403/451 on the profile README gives step `skipped` and keeps the earlier README and flag; a repository deleted before the topics step does not fail the sync; after a rename on GitHub, `/auth/me` returns the new username and avatar; a renamed contributed repository (301) is stored under its new name and linked as contributor

## 3. Sign-in identity (D5, A-14)

- [x] 3.1 `fetch_identity`: guard `response.json()`, require a dict with `id` and a non-empty `login`; `ValueError`/`TypeError`/`KeyError` → `OAuthError("identity_failed", ...)`
- [x] 3.2 Tests (`test_github_auth.py`): a non-JSON 200 and a JSON 200 without `id` each redirect with `auth_error=failed`, write an audit entry with no token, create no session and store no token

## 4. Manifests and repository analysis (D6, D7, B-13, C-1)

- [x] 4.1 `parse_manifest`: catch `RecursionError` with the other parse errors
- [x] 4.2 `services/repositories/analysis.py`: ordered `ERROR_CODES` with `GitHubClientError` → `client_error` after its subclasses; `(KeyError, ValueError, TypeError, IndexError)` from `_fetch` → `lifecycle.fail(repo, "invalid_response")`, logging repository and exception type only; rate limit, transient, auth, `JobCancelled`, `ClaimLost`, `DatabaseError` and other exceptions still release and re-raise; update the module docstring and the "follows renames" comment
- [x] 4.3 Tests (`test_profiling_manifests.py`): deeply nested `package.json`, `pyproject.toml` and `Cargo.toml` each return `[]`; a repository with one such manifest and a valid `requirements.txt` stores only the latter's dependencies
- [x] 4.4 Tests (`test_repository_analysis.py`, `test_discovery_service.py`): a 400 on one candidate marks it FAILED `client_error` and discovery completes with the others analyzed; a metadata payload missing `id` marks it FAILED `invalid_response`; a 451 keeps `unavailable`; a secondary-limit 403 on contributors releases the repository to its previous state (not FAILED, eligibility unchanged); a 301 rename completes with the same GitHub ID and the new full name; an `AttributeError` raised inside `_fetch` still propagates

## 5. Refresh failures recorded (D8, C-9)

- [x] 5.1 Add `Repository.refresh_failed_at` (null) and a `repositories` migration
- [x] 5.2 `lifecycle.record_refresh_failure(repo_id, code)`: one UPDATE excluding in-progress and FAILED states, setting `lifecycle_error` and `refresh_failed_at`; `complete` and `fail` clear `refresh_failed_at`
- [x] 5.3 `_refresh`: on `Fail(code)` call `record_refresh_failure`; keep the app-credentials `GitHubAuthError` path log-only
- [x] 5.4 Setting `REPO_REFRESH_RETRY_MINUTES` (default 60) in `base.py` and `.env.example`; add it to the `core.E020` positive-integer list
- [x] 5.5 `process_repository_backlog`: exclude rows with `refresh_failed_at >= now - REPO_REFRESH_RETRY_MINUTES`
- [x] 5.6 Tests (`test_repository_analysis.py`, next to the refresh tests): a STALE repository whose refresh fails `github_unavailable` stays STALE and eligible with that `lifecycle_error`, is not queued by the next backlog run, is queued after the delay, and a completed refresh clears the error and `refresh_failed_at`; a repository claimed by another worker is not touched by `record_refresh_failure`; a FAILED repository's retry still follows `REPO_FAILED_RETRY_HOURS`

## 6. Request path without Redis (D9, H-1)

- [x] 6.1 `SESSION_ENGINE = "django.contrib.sessions.backends.db"`
- [x] 6.2 `core/throttling.py`: `FailOpenMixin` with a cache proxy that raises `_CacheUnavailable` on cache errors, a module-level backoff (`THROTTLE_CACHE_BACKOFF_SECONDS`, monotonic clock) and one warning per failure with the exception type only; `AnonRateThrottle`, `UserRateThrottle`, `ScopedRateThrottle` subclasses
- [x] 6.3 `DEFAULT_THROTTLE_CLASSES` → the `core.throttling` classes; setting `THROTTLE_CACHE_BACKOFF_SECONDS` (default 30) in `base.py` and `.env.example`; add it to `core.E020`
- [x] 6.4 Tests (`test_api_platform.py`): with the throttle cache raising `ConnectionError`, a signed-in `GET /api/v1/recommendations` returns 200, a second request within the backoff does not touch the cache, and a warning is logged without request data; after the backoff with a working cache, a client over the limit gets 429 `throttled`; a session created before switching engines (row in `django_session`) still authenticates; existing throttle and spoofed-header tests still pass

## 7. Verification and housekeeping

- [x] 7.1 `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`
- [x] 7.2 `npm run api:sync` and confirm the OpenAPI schema and `schema.d.ts` are unchanged
- [x] 7.3 Mark rows A-2, A-3, A-4, A-5, A-6, A-11, A-13, A-14, B-13, C-1, C-6, C-9 and H-1 (including the `cached_db` extra) `fixed (github-error-resilience)` in `Bug_Backlog.md`
- [x] 7.4 Release housekeeping per CLAUDE.md §8 as patch `0.12.5`: version files and lockfiles, `npm run check:version`, `CHANGELOG.md`, `features.txt`, `README.md` status line, and the CLAUDE.md §7 entry (with K-1 still carried over)
