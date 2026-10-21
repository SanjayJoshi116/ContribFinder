# Bug Backlog

Findings from the codebase sweep on 2026-10-19 (v0.12.0, `main` @ 50acbb8).
Status: `open` · `in-progress` · `fixed` · `wontfix`.

## Known gaps (already tracked elsewhere)

| ID | Item | Source | Status |
|---|---|---|---|
| K-1 | Judge `real-a-v2`, build `benchmark-v2`, evaluate v1/v2 (all/persona/real), `--write-baseline`. Blocks any further ranking search. | features.txt:261, CLAUDE.md §7 | open |
| K-2 | Docker Compose verification from a fresh `.env` (no Docker on dev machine). | features.txt:279 | open |
| K-3 | Issue-level evaluation (benchmark covers repositories only). | features.txt:282 | open |
| K-4 | Docs-style repositories with a code language and no list topic (`system-design-primer`, `developer-roadmap`) pass `not_code`. Since 0.12.7 a suspected list (`awesome-*`, list topic) that declares manifest dependencies (lint or site tooling) passes too. | CHANGELOG 0.12.0, 0.12.7 | open (known limit; `ideas.md` §11) |
| K-5 | Active config v2 is not an improvement over v1 on `benchmark-v1` (NDCG@10 +0.0195, P@5 −0.0333). | CLAUDE.md Phase 8b | open (needs K-1) |

## Documentation drift

| ID | Item | Where | Status |
|---|---|---|---|
| DOC-1 | Ctrl+C issue still `[~] carried to Phase 5`; fixed in Phase 8a per CLAUDE.md §6, no `[x]` entry records it. | features.txt:130 | open |
| DOC-2 | Carry-over says "real-a exported, 3 of 39 graded"; current target is `real-a-v2` (40 candidates). The 3 grades are likely in the stale `real-a.csv`. | features.txt:261 | open |

## Code review findings

Source: `code-review` (high, `apps/`, all findings). **Scope caveat:** the review covered only the
last commit (`HEAD~1..HEAD`, 50acbb8: benchmark tooling and discovery size mix), not the whole
codebase. All rows verified against the code (2026-10-19); see Verification notes. Ranked most
severe first.

| ID | File | Finding | Failure scenario | Status |
|---|---|---|---|---|
| R-1 | `apps/backend/recommendations/management/commands/evaluate_ranking.py:77` | `--write-baseline` without `--dataset` evaluates the selection dataset (benchmark-v2 once present), so the documented baseline fix never rewrites the benchmark-v1 entry that CI checks. | With a local benchmark-v2, `evaluate_ranking --write-baseline` rewrites only `datasets.benchmark-v2`; CI skips v2 and `test_baseline_metrics_unchanged` fails on stale v1. Workaround: `--dataset evaluation/benchmark-v1.json`. | fixed (evaluation-tooling-integrity) |
| R-2 | `apps/backend/services/evaluation/baseline.py:42` | Format 3 keeps other datasets' entries but stores one global `top_n` from the current run. | v1 written at top_n 50, then `--dataset holdout-v2 --write-baseline --top-n 20` sets `top_n: 20` globally; the test re-evaluates v1 at 20 against metrics from 50 and reports a false "Ranking changed". Store `top_n` per dataset. | fixed (evaluation-tooling-integrity) |
| R-3 | `apps/backend/config/settings/base.py:279` | Default `DISCOVERY_STAR_BANDS` hardcodes 20 instead of deriving from `DISCOVERY_MIN_STARS`; system check requires a match. | Set only `DISCOVERY_MIN_STARS=50` → `core.E025` fails, Django refuses to start (runserver, migrate, worker). | fixed (discovery-repository-data) |
| R-4 | `apps/backend/services/discovery/service.py:305` | `_remove_not_code` writes lifecycle and eligibility directly, overwriting existing reasons and racing with an in-progress analysis claim. | (a) FAILED or archived repository loses its real `ineligible_reason`. (b) REFRESHING repository (previous RECOMMENDABLE) is marked ineligible, analysis fails transiently, `lifecycle.release()` restores RECOMMENDABLE → RECOMMENDABLE but ineligible. Move to `services/repositories/lifecycle.py`. | fixed (discovery-repository-data) |
| R-5 | `apps/backend/services/discovery/filters.py:116` | `not_code` treats any `awesome-*` name and generic topics (`list`, `lists`, `books`) as non-code; ineligibility is set on the shared Repository row. | `sindresorhus/awesome-lint` (a linter) is rejected; a linked-list library tagged `list` is rejected; it disappears for every user despite having a primary language. | fixed (discovery-repository-data) |
| R-6 | `apps/backend/services/discovery/queries.py:172` | Provenance `core` includes the star band; a repository crossing a band creates a new CandidateDiscovery row and the old one (with its old search_rank) is never updated or pruned. | Rank #1 at `stars:20..999`, grows to rank #28 at `>=1000`; `Min(search_rank)` stays 1, so the stale rank keeps analysis priority and survives the pool cap. Band qualifier also leaks into user-facing provenance. | fixed (discovery-repository-data) |
| R-7 | `apps/backend/services/evaluation/sheet.py:94` | `read_sheet` drops every physical line starting with `#` before CSV parsing, including continuation lines inside quoted multi-line fields. | Description `"Fast parser\n# Features"` loses its closing line and grade; quoted field swallows the next row → lost or misattributed grade, or a confusing "not a candidate" error. | fixed (evaluation-tooling-integrity) |
| R-8 | `apps/backend/services/evaluation/sheet.py:98` | Duplicate repository rows: last wins silently. Formatted empty rows (`,,,,,,,,,`) become repository `''` and fail the whole import. | Spreadsheet saves trailing blank rows → `Row : not a candidate of this export`, nothing imported. | fixed (evaluation-tooling-integrity) |
| R-9 | `apps/backend/services/discovery/service.py:440` | `_band_counts` assigns stars to the highest band whose low is reached, ignoring that band's high. | Bands `[[20,99],[200,999]]` (allowed by the check): 150 stars → `20..99`; 5000 stars → `200..999`. `pool_bands` metadata wrong. | fixed (discovery-repository-data) |
| R-10 | `apps/backend/services/discovery/queries.py:164` | Request budget floor-divided by band count; remainder silently wasted; check accepts non-multiples. | `DISCOVERY_MAX_QUERIES=25`, 3 bands → 24 requests; 5 with 3 bands → one query. No warning. | fixed (discovery-repository-data) |
| R-11 | `apps/backend/services/discovery/filters.py:126` | `_topics` uses `values_list`, which bypasses prefetch → N+1 in `_step_interactions`; `_remove_not_code` duplicates the topic extraction. | One extra query per contributed repository (up to `GITHUB_CONTRIB_MAX_REPOS`). Fix: `repo.topics.all()` + `prefetch_related('topics')`. Docstring still says "Pure functions". | fixed (discovery-repository-data) |
| R-12 | `apps/backend/services/discovery/service.py:285` | Design: pool step re-checks only `not_code` on stored data; other eligibility rules go stale when settings change. | After changing `DISCOVERY_MAX_PUSH_AGE_DAYS` or license rules, RECOMMENDABLE repositories keep old eligibility until re-analysis. Re-run `eligibility()` via a lifecycle helper (would also fix R-4). | fixed (discovery-repository-data) |
| R-13 | `apps/backend/services/evaluation/build.py:34` | `build` assumes each input is a JSON object; a top-level list raises uncaught `AttributeError`. Differing `format` merged unchecked until final `parse`. | `build_benchmark --input report.json` (array) → raw traceback instead of `CommandError`. | fixed (evaluation-tooling-integrity) |
| R-14 | `apps/backend/recommendations/management/commands/build_benchmark.py:174` | Real developers keep the export description "Add judgments ... by hand before using this developer"; `import_sheet` does not update it. | Committed benchmark-v2 shows judged developers labeled as unjudged. | fixed (evaluation-tooling-integrity) |

## Batch 5 review (2026-10-21)

Source: `code-review` over the uncommitted `github-error-resilience` diff (v0.12.5), plus the
`/simplify` altitude pass (V-1 overlap). Verified against the code 2026-10-21 (V-5, V-6 partial: narrow windows; V-8 matches the metadata convention) and fixed in 0.12.5 before commit. Paths under
`apps/backend/`. Ranked most severe first. Type: bug · gap · design · cleanup.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| V-1 | design | `services/repositories/analysis.py:69` | `ERROR_CODES` maps bare `KeyError`/`ValueError`/`TypeError`/`IndexError` → FAILED `invalid_response`. Also catches transient bad bodies (truncated/HTML 200 → `JSONDecodeError`), corrupt ETag cache entries and programming bugs → every analyzed repository FAILED and ineligible for `REPO_FAILED_RETRY_HOURS`, logged at INFO. Deeper fix: raise typed `GitHubInvalidResponse(GitHubClientError)` at the `.json()`/`from_api` boundary in `services/github`; sync's `SKIPPABLE` and `oauth.fetch_identity` then get it for free. Module docstring also outdated. | fixed (github-error-resilience) |
| V-2 | bug | `services/github/client.py:545` | Redirect guard in `_send` compares host only, not scheme/port. `Location: http://api.github.com/...` passes → bearer token sent in cleartext. Compare origin (scheme, host, port) with `GITHUB_API_BASE_URL`. | fixed (github-error-resilience) |
| V-3 | design | `core/throttling.py:55` | Fail-open applies to every throttle, incl. anon throttle on `/auth/github` and scoped `/profile/sync`. Redis down (or induced cache errors) → no rate limiting per process for `THROTTLE_CACHE_BACKOFF_SECONDS`, renewed each error → OAuth-state churn, sync flooding into GitHub. Sensitive scopes: fail closed or in-process fallback counter. Revisits design D9. | fixed (github-error-resilience) |
| V-4 | gap | `repositories/tasks.py:98` | `_refresh`'s app-credentials `GitHubAuthError` branch stays log-only (task 5.3), so `refresh_failed_at` stays null → rejected/rotated `GITHUB_CLIENT_SECRET` requeues the same `REPO_REFRESH_BATCH` every beat, the loop C-9 fixed for other errors. | fixed (github-error-resilience) |
| V-5 | bug | `services/repositories/lifecycle.py:116` | `record_refresh_failure` runs as a separate UPDATE after `release()`. Another analysis can claim + complete in between → stale `lifecycle_error` and `refresh_failed_at` land on fresh RECOMMENDABLE data, next refresh delayed up to 60 min. Record inside `release()` under the held claim token. | fixed (github-error-resilience) |
| V-6 | bug | `repositories/tasks.py:81` | `.exclude(refresh_failed_at__gte=...)` applies to the whole backlog query → also hides abandoned claims (dead worker, stuck FETCHING/REFRESHING) and DISCOVERED rows for up to `REPO_REFRESH_RETRY_MINUTES`. Scope it to the STALE branch. | fixed (github-error-resilience) |
| V-7 | bug | `services/github/oauth.py:113` | `str(data["login"])` turns JSON `null` into `"None"`, passing the non-empty check → account upserted with username `"None"`. Check `isinstance(login, str)` and non-empty before converting. | fixed (github-error-resilience) |
| V-8 | cleanup | `services/github/sync.py:187` | `languages_skipped` written to job metadata, never read (no code, API or UI). Spec-required (task 2.1), so: surface it (step detail or warning) or drop it from the spec. | wontfix (internal diagnostics, like `repos_capped`; spec-required) |
| V-9 | cleanup | `services/github/sync.py:190` | `/simplify` altitude: `_step_topics` re-checks existing pks to work around topics being written a step later from `job.metadata["repo_topics"]`. Writing topics in `_step_repositories`' `job_write` removes the race (and rename re-points) and the metadata copy; `_step_topics` stays as a no-op step. Design accepted A-11 as partial. | fixed (github-error-resilience) |

## Batch 6 review (2026-10-21)

Source: `code-review` over the uncommitted `recommendation-consistency` diff (v0.12.6). Paths
under `apps/backend/`. All fixed in 0.12.6 before commit.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| W-1 | bug | `services/feedback.py` (`dismiss`) | Events referenced a recommendation a concurrent generation deleted → deferred FK fails at commit → dismiss 500. | fixed (recommendation-consistency) |
| W-2 | bug | `services/feedback.py` (`record`) | Same for `viewed` (and other events), with the profile lock widening the window. | fixed (recommendation-consistency) |
| W-3 | bug | `services/repositories/analysis.py` (`_store_issues`) | Only deleted issues were locked by pk; the unordered `bulk_update` of open issues could deadlock with persist's pk-ordered lock. | fixed (recommendation-consistency) |
| W-4 | perf | `services/ranking/freshness.py` | The sweep flagged running generations as due → `rerun_requested` → a redundant generation after every overlap. | fixed (recommendation-consistency) |
| W-5 | gap | `services/jobs.py` | A retry reloads its inputs but kept the rerun flag (extra run). A flag lost on permanent failure stays an accepted risk (design). | fixed (recommendation-consistency) |
| W-6 | gap | `services/ranking/freshness.py` | A staleness mark overwrote the completion time of an analysis newer than the last generation → missed regeneration. | fixed (recommendation-consistency) |
| W-7 | gap | `services/ranking/freshness.py` | A generation that keeps failing was restarted every sweep (30 min) forever. | fixed (recommendation-consistency) |
| W-8 | bug | `services/ranking/service.py` | An issue re-analyzed (not deleted) between ranking and storing passed the check → reasons from stale analysis. | fixed (recommendation-consistency) |
| W-9 | gap | `services/feedback.py` (`save`) | Dismissal enforced only through the recommendation's deletion. | fixed (recommendation-consistency) |
| W-10 | perf | `services/feedback.py` (`record`) | View de-duplication waited on the profile lock held by a whole persist. | fixed (recommendation-consistency) |

## Batch 7 review (2026-10-21)

Source: `code-review` over the uncommitted `discovery-repository-data` diff (v0.12.7). Paths
under `apps/backend/`. Verified against the code; fixed in 0.12.7 before commit unless noted.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| X-1 | bug | `services/repositories/lifecycle.py` (`release_name`) | A holder that gave up its name stayed eligible: recommended as `a/b~5` with a URL that now opens another repository. Now ineligible `name_released` (INDEXED) until resolved. | fixed (discovery-repository-data) |
| X-2 | bug | `services/discovery/service.py` (`_prune_discoveries`) | A run with no search (empty plan) or a query rejected with 422 pruned valid records, leaving candidates with no provenance. | fixed (discovery-repository-data) |
| X-3 | gap | `services/discovery/service.py` (`_step_pool`) | Pool writes (prune, not_code, re-check, eviction) ran outside `job_write`: a cancelled or reclaimed run kept writing. | fixed (discovery-repository-data) |
| X-4 | perf | `services/repositories/analysis.py` (`run`) | A queued refresh with nothing stale left still completed and stamped a transition → needless regenerations for every developer. Now released, SKIPPED. | fixed (discovery-repository-data) |
| X-5 | bug | `services/discovery/service.py` (`_record`) | One query matching a repository in both bands in one run kept the later band's rank. Now the better rank within a run. | fixed (discovery-repository-data) |
| X-6 | bug | `services/repositories/backlog.py` (`queue_batch`) | Overlapping backlog runs could queue the same rows. Now selected `skip_locked` and stamped in one transaction. | fixed (discovery-repository-data) |
| X-7 | design | `services/github/storage.py` (`upsert_repository`) | `release_name` locks a second row outside GitHub ID order; deadlock needs a rename race plus two concurrent runs (accepted in design D3; the old delete had the same shape). | wontfix (accepted) |
| X-8 | cleanup | `services/discovery/service.py` (`_step_pool`) | `_remove_not_code` and `recheck_eligibility` both load the pool with topics and dependencies. Not one pass: they cover different lifecycles. | wontfix (batch 11 if it matters) |
| X-9 | design | `services/discovery/service.py` (steps) | A suspected list found `not_code` by this run's analysis keeps its pool slot until the next run (pool runs before analysis, D7). | wontfix (by design) |
| X-10 | — | `core/checks.py` | "W003 when the budget is below the band count": E025 already errors there and W003 is skipped. | false-positive |
| X-11 | perf | `services/repositories/lifecycle.py` (`complete`) | Eligibility re-reads the topics and dependencies the analysis just wrote: 1–2 queries per analysis. Passing them in needs an annotation set by hand (skipped in the `/simplify` pass). | open (batch 11) |
| X-12 | cleanup | `tests/` | `developer`, `single_band` and `client` fixtures are copied across `test_discovery_service.py`, `test_discovery_repository_data.py`, `test_repository_analysis.py` and `test_issue_ingestion.py`; move them to `conftest.py` (`fresh_repo` and `analyze` already moved to `repo_fixtures.py`). | open (batch 11) |

## Batch 9 review (2026-10-21)

Source: `code-review` over the uncommitted `frontend-correctness` diff (v0.12.8). Paths under
`apps/frontend/src/` unless noted. Y-1…Y-5 and Y-8 fixed in 0.12.8 before commit, each with a
test that fails without the fix (Y-8 checked by `npm run e2e`).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| Y-1 | bug | `app/queryClient.ts` (401 handler) | Log out, disconnect or delete account while a poll is in flight: its 401 called `endSession` → "Your session ended" after a deliberate sign-out. Sign-out mutations now carry `meta.endsSession` (`features/auth/api.ts`), which suspends the handler until it fails or `/auth/me` succeeds again. | fixed (frontend-correctness) |
| Y-2 | bug | `app/jobTransitions.ts` (`fetchStatusAndRefresh`) | The status `queryFn` awaited the whole refresh cascade (which includes other status queries); one slow or hung derived request froze the status and its polling. Refresh is now started, not awaited. | fixed (frontend-correctness) |
| Y-3 | bug | `lib/useScrollToHash.ts` | `decodeURIComponent` threw on a malformed hash (`#%E0`) inside an effect → blank page. Falls back to the raw hash. | fixed (frontend-correctness) |
| Y-4 | bug | `features/recommendations/RecommendationList.tsx` (page recovery) | Dismissing the last card on page N moved to page N−1 from the optimistic cache; a failed dismissal restored the card on a page no longer shown. Recovery now waits for pending dismissals (`dismissMutationKey`). | fixed (frontend-correctness) |
| Y-5 | bug | `lib/utils.ts` (`positiveId`) | `Number()` accepted `0x1f`, `1e2`, ` 7` → `/app/recommendations/0x1f` fetched id 31. Now decimal digits only. | fixed (frontend-correctness) |
| Y-6 | design | `app/queryClient.ts` (`DERIVED_STALE_TIME_MS`) | Data changed by jobs no status query watches (a standalone `profile_analysis` from `reanalyze_profiles`, a backend repository refresh) stays cached up to 5 min where it used to refetch on mount. Intended trade-off of F-1; fix if it shows in use (watch the analysis job too, or a shorter stale time for profile and detail; `ideas.md` §14). | open |
| Y-7 | bug | `features/feedback/api.ts` (`usePagedList`) | Saved and hidden lists page by number: a save or unsave in another tab between "Show more" clicks shifts the pages → a duplicated entry (duplicate React key) or a skipped one. Needs cursor or `saved_at`-keyset pagination in the API, or de-duplication by `repository_id` (`ideas.md` §14). | open |
| Y-8 | bug | `apps/backend/config/settings/e2e.py` | Claimed self-contained but `base.py` read the whole local `.env` (`NUM_PROXIES`, `ALLOWED_HOSTS`, `DISCOVERY_MAX_POOL`, ranking settings used by the seed): local e2e differed from CI. The runner (`scripts/e2e-backend.mjs`) passes only `DATABASE_URL` from `.env` and sets `DJANGO_READ_DOTENV=0`, which `base.py` honors. | fixed (frontend-correctness) |
| Y-9 | cleanup | `apps/backend/e2e/management/commands/e2e_seed.py` | An installed app's command imports `tests.repo_fixtures`; a test-helper refactor breaks `npm run e2e` while pytest stays green. Move the shared seeding helpers to a module both use. | open (batch 11) |
| Y-10 | cleanup | `app/app.test.tsx` (`count`) | Reimplements `callsTo` from `features/feedback/feedback.test.tsx`; move one helper to `test/render.tsx`. | open (batch 11) |

## Full-file reviews (2026-10-19)

`code-review` at high effort over whole files, all findings reported. All rows verified against
the code by a second, adversarial pass (2026-10-19); see Verification notes. Cited line numbers
are often stale: use the corrected lines there, or search for the symbol. Paths are under `apps/backend/` (areas A-E), `apps/frontend/src/` (F) and
the repository root (G). Within each area, rows are ordered most severe first. Type: bug · gap (spec/rule violation) · perf · cleanup.

### A: Auth, tokens, GitHub client and sync, data deletion

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| A-1 | bug | `services/data_deletion.py:54` | Deletion only flips job status; a sync mid-step keeps the decrypted token and writes GitHubProfile, repositories or DeveloperProfile after the deletion commits → deleted data returns, and GitHub calls run after disconnect. | fixed (privacy-deletion-finality) |
| A-2 | bug | `services/github/client.py:584` | A secondary-rate-limit 403 without Retry-After and with remaining > 0 → `GitHubForbidden`, not `GitHubRateLimited`. `count_contributors` returns None, SKIPPABLE steps drop data, and other paths fail as `github_error`. Rate limit is treated as empty data. | fixed (github-error-resilience) |
| A-3 | bug | `services/github/sync.py:165` | `_step_languages` catches only 404; one owned repository returning 403 or 451 (DMCA) fails every sync permanently → no analysis, discovery or recommendations. | fixed (github-error-resilience) |
| A-4 | bug | `services/github/client.py:524` | Redirects not followed; the 301 for a renamed repository → `GitHubClientError`. Contribution evidence dropped; the languages step fails the whole sync; discovery fails too (see C-1). | fixed (github-error-resilience) |
| A-5 | bug | `services/github/sync.py:117` | `_step_readme` treats only 404 as "no README"; a 403 or 451 on `{login}/{login}` fails the sync. Violates the rule that a README failure degrades gracefully. | fixed (github-error-resilience) |
| A-6 | bug | `services/crypto.py:45` | `TokenDecryptionError` is not a `GitHubError`; after a key rotation drops an old key, syncs fail as `internal_error`, not `github_auth_invalid` → user is never prompted to sign in again. | fixed (github-error-resilience) |
| A-7 | gap | `accounts/views.py:130` | SIGN_IN audit metadata keeps `github_id` and `github_username`; account deletion only nulls the user FK → GitHub identity survives "delete account" (FR-DATA-003). | fixed (privacy-deletion-finality) |
| A-8 | gap | `services/github/accounts.py:31` | `User.display_name` (real name from GitHub) is not cleared by disconnect or delete-data; still served by `/auth/me`. | fixed (privacy-deletion-finality) |
| A-9 | gap | `services/github/accounts.py:35` | Re-sign-in stores the new token without revoking the old one → orphaned valid tokens until disconnect. | fixed (privacy-deletion-finality) |
| A-10 | bug | `services/github/storage.py:26` | `upsert_repository` (`update_or_create` on github_id) races on concurrent create → IntegrityError → `internal_error`, not retried; the user's job fails. | false-positive |
| A-11 | bug | `services/github/sync.py:178` | `_step_topics` inserts for repository pks saved earlier in metadata; if the row was deleted in between (full_name conflict, orphan cleanup) → FK IntegrityError → sync fails permanently. | fixed (github-error-resilience) |
| A-12 | bug | `accounts/views.py:214` | Disconnect logs out only the current session; other sessions stay valid up to 14 days with no GitHub account. | fixed (privacy-deletion-finality) |
| A-13 | bug | `services/github/sync.py:96` | Sync refreshes `GitHubProfile.login/avatar_url` but not `GitHubAccount.username/avatar_url` (what `/auth/me` serves) → stale login after a GitHub rename until the next sign-in. | fixed (github-error-resilience) |
| A-14 | bug | `services/github/oauth.py:107` | `fetch_identity` does not guard `response.json()` or `data['id'/'login']` → malformed 200 gives a JSON 500 instead of an `auth_error=failed` redirect plus audit entry. | fixed (github-error-resilience) |
| A-15 | bug | `accounts/views.py:75` | One OAuth state per session; signing in from a second tab overwrites it → first tab's callback fails `invalid_state`. | fixed (security-hardening) |
| A-16 | perf | `services/github/client.py:530` | `github:ratelimit:{scope}` written on every response but never read; keyed per scope, not per credential (user `PUBLIC_SCOPE` overwrites the app's). | confirmed |
| A-17 | perf | `services/github/client.py:511` | A 304 does not refresh the ETag cache TTL → valid entries expire at `GITHUB_ETAG_TTL`, forcing a counted 200 refetch. Use `cache.touch`. | confirmed |
| A-18 | perf | `services/github/sync.py:79` | Profile sync caches public repository endpoints in the per-user scope, not `PUBLIC_SCOPE` → data duplicated per user, fewer 304 hits. | confirmed |
| A-19 | cleanup | `accounts/views.py:183` | `cancel_active_syncs` runs twice on disconnect and account deletion (`_revoke_and_unlink` + `delete_github_data`). | fixed (privacy-deletion-finality) |
| A-20 | perf | `core/health.py:31` | `check_redis` creates a new Redis client and pool on every health request. | confirmed |

### B: Jobs, developer profiling

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| B-1 | bug | `services/jobs.py:150` | PENDING and RETRYING jobs never expire or recover (only RUNNING does). A lost Redis message → zombie job, blocked by the unique constraint → user can never sync, discover or regenerate again. | fixed (job-claim-fencing) |
| B-2 | bug | `services/jobs.py:44` | `claim_job` reclaims a stale RUNNING job without fencing; `heartbeat`/`finish_job` don't check ownership → a slow (not dead) worker and the new one both write; first to finish fires `on_completed`. Needs a claim token. | fixed (job-claim-fencing) |
| B-3 | bug | `services/profiling/analysis.py:218` | Shared Skill and Interest rows upserted (`ON CONFLICT DO UPDATE`) in confidence order inside per-user transactions → concurrent analyses deadlock → `analysis_failed`, not retried. Sort slugs, or upsert outside the transaction. | fixed (job-claim-fencing) |
| B-4 | bug | `services/profiling/analysis.py:257` | `_persist` uses `get_or_create`; an analysis running during delete-data recreates DeveloperProfile and README evidence (see A-1). | fixed (privacy-deletion-finality) |
| B-5 | bug | `services/profiling/analysis.py:249` | Input snapshot read without a lock and `_persist` overwrites unconditionally → overlapping sync analysis and standalone `profile_analysis` can let the older snapshot win. | fixed (job-claim-fencing) |
| B-6 | bug | `services/profiling/experience.py:58` | Cutoffs 0.67/1.34 are not the documented rounded mean: (1,1,0) mean 0.667 → beginner (should be intermediate); 1.4 → experienced. Feeds `difficulty_fit`. | confirmed |
| B-7 | bug | `services/jobs.py:250` | `start_profile_analysis` treats stale RUNNING jobs as active (no stale exclusion or `_expire_stale`, unlike the other start_*) → `reanalyze_profiles` skips users for up to about 15 min after a crash. | fixed (job-claim-fencing) |
| B-8 | bug | `services/jobs.py:240` | IntegrityError fallback re-queries the active job, which may have finished meanwhile → `.get()` raises DoesNotExist (500 on POST /profile/sync); `.first()` returns None, read as "no profile". | fixed (job-claim-fencing) |
| B-9 | bug | `services/jobs.py:119` | Eager mode (`REDIS_URL` empty): `task.retry(countdown)` re-runs inline, ignoring the countdown → 5 back-to-back GitHub calls on 5xx or 429, a hot loop. | fixed (job-claim-fencing) |
| B-10 | bug | `services/jobs.py:50` | `claim_job` ignores `attempts` → broker redelivery can exceed `SYNC_MAX_ATTEMPTS` (crash loop continues). | fixed (job-claim-fencing) |
| B-11 | bug | `services/jobs.py:183` | Recovery, expiry and cancel don't update `steps` → a FAILED or CANCELLED job still shows a step `running` (UI spinner on a dead job). | fixed (job-claim-fencing) |
| B-12 | bug | `services/jobs.py:174` | `recover_stale_jobs` re-sends `.delay` every beat without changing status → duplicate messages in a busy queue, repeated misleading log. | fixed (job-claim-fencing) |
| B-13 | bug | `services/profiling/manifests.py:161` | `parse_manifest` doesn't catch RecursionError or MemoryError → a deeply nested package.json fails the dependencies step. | fixed (github-error-resilience) |
| B-14 | bug | `services/profiling/readme.py:32` | `_URLS` keeps `&amp;` → `parse_qs` keys like `amp;logo`; second and later badge params lost (e.g. Go not detected). | confirmed |
| B-15 | bug | `services/profiling/readme.py:93` | shields.io parser reads only the first dash segment; `/badge/-Python-...` or `/badge/language-Rust-...` without `logo=` → no evidence. | confirmed |
| B-16 | bug | `services/profiling/interests.py:33` | Contribution interest evidence uses `repo.pushed_at`, not `last_contributed_at` → "last observed" overstates recency. | confirmed |
| B-17 | perf | `developers/api.py:44` | Two `Count(distinct=True)` over skills and interests joins → cross product (150×40 = 6,000 rows) per profile read. | confirmed |
| B-18 | cleanup | `developers/tasks.py:15` | `extract_developer_skills` re-implements `run_tracked_job` by hand; lifecycle fixes (B-2, B-11) must be made twice; task isn't a thin wrapper. | fixed (job-claim-fencing) |
| B-19 | cleanup | `services/jobs.py:277` | Four copy-pasted start_* functions have drifted (causes B-7 and B-8). Extract `_start_job`. | fixed (job-claim-fencing) |
| B-20 | cleanup | `services/profiling/summary.py:28` | Docstring says languages are "by bytes"; callers pass them by confidence on purpose. | confirmed |

### C: Repositories, discovery

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| C-1 | bug | `services/repositories/analysis.py:142` | A non-permanent, non-transient client error (301 rename) re-raises → the whole discovery job fails, no lifecycle error recorded; every user whose pool holds the repository fails; backlog requeues forever. The "follows renames" comment (l.161) is wrong. | fixed (github-error-resilience) |
| C-2 | bug | `services/discovery/service.py:364` | `upsert_repository` deletes any other row with the same full_name → a live renamed repository is wiped, cascading to every user's candidates, recommendations, saves and dismissals. | fixed (discovery-repository-data) |
| C-3 | bug | `services/repositories/lifecycle.py:363` | `release/fail/complete` don't check claim ownership → a reclaimed-stale worker overwrites lifecycle while another analyzes; final state = last writer. | fixed (job-claim-fencing) |
| C-4 | bug | `services/repositories/analysis.py:136` | Repository claim never renewed during `_fetch` → analyses longer than 10 min are reclaimed while running (duplicate work, plus C-3). | fixed (job-claim-fencing) |
| C-5 | bug | `services/repositories/analysis.py:129` | Explicit `parts` skip the FAILED→recheck-all rule, and `complete()` sets INDEXED before `eligibility()` → a deleted (404) repository returns as RECOMMENDABLE, eligible. | fixed (discovery-repository-data) |
| C-6 | bug | `services/repositories/analysis.py:56` | `GitHubForbidden` treated as permanent; a secondary-limit 403 (see A-2) marks shared repositories FAILED and ineligible for all users for 24 h. | fixed (github-error-resilience) |
| C-7 | bug | `services/discovery/service.py:137` | Each query's results are upserted in one transaction; concurrent jobs lock the same rows in different orders → deadlock → `internal_error`, job fails. | fixed (discovery-repository-data) |
| C-8 | bug | `services/discovery/service.py:364` | Search upserts set `synced_at=now` → `metadata` never stale for frequently found repositories → languages never refreshed. | fixed (discovery-repository-data) |
| C-9 | bug | `repositories/tasks.py:384` | Non-retryable refresh failure only logged; repository restored with no `lifecycle_error` → breaks "failures are state"; backlog retries forever. | fixed (github-error-resilience) |
| C-10 | bug | `services/repositories/lifecycle.py:371` | `release()` sets `lifecycle_changed_at=now` → a transient error restarts the FAILED 24 h clock and the DISCOVERED grace period. | fixed (job-claim-fencing) |
| C-11 | bug | `services/discovery/service.py:61` | Analysis step runs before the pool step → budget spent on candidates the pool deletes; ordering also differs (pool adds `last_seen_at`). | fixed (discovery-repository-data) |
| C-12 | bug | `services/discovery/service.py:180` | On resume `pending` excludes already analyzed repositories, so `pending[:cap]` takes new ones → more than `DISCOVERY_MAX_ANALYSES_PER_RUN` per run; `analysis_total` overwritten. | fixed (discovery-repository-data) |
| C-13 | bug | `services/discovery/service.py:262` | CandidateDiscovery rows from queries that no longer match are never pruned → stale best rank drives analysis order and eviction (generalizes R-6). | fixed (discovery-repository-data) |
| C-14 | bug | `services/repositories/lifecycle.py:396` | Without a metadata fetch, `complete()` computes eligibility from the in-memory row loaded at claim, ignoring concurrent upserts. | fixed (discovery-repository-data) |
| C-15 | perf | `repositories/tasks.py:357` | Backlog requeues STALE repositories every 15 min even when a task is queued or retrying; explicit-part tasks don't intersect with current stale parts → duplicate fetches. | fixed (discovery-repository-data) |
| C-16 | gap | `repositories/tasks.py:313` | Staleness and backlog selection logic lives in Celery tasks, not services (CLAUDE.md §5). | fixed (discovery-repository-data) |
| C-17 | cleanup | `repositories/api.py:112` | Candidate ordering written three times (API, `_pool_repositories`, `_step_pool`) and drifted. | fixed (discovery-repository-data) |
| C-18 | cleanup | `services/discovery/service.py:366` | Null `lifecycle_changed_at` patched in two places; give the field a default. | fixed (discovery-repository-data) |
| C-19 | bug | `services/repositories/lifecycle.py:365` | `release()` is read-then-update (not atomic); can restore a stale `previous_lifecycle`. | fixed (job-claim-fencing) |
| C-20 | perf | `services/discovery/service.py:184` | Full metadata JSON rewritten after each analysis → quadratic write volume. | confirmed |
| C-21 | cleanup | `repositories/serializers.py:58` | `ineligible_reason` not `read_only=True` → OpenAPI marks it writable and required. | confirmed |
| C-22 | perf | `services/repositories/lifecycle.py:393` | `complete()` saves ANALYZED and INDEXED separately (unobservable) → 2 wasted UPDATEs per analysis. | fixed (job-claim-fencing) |
| C-23 | cleanup | `repositories/tasks.py:309` | `_has_app_credentials` duplicates `GitHubClient.for_app()`'s check. | confirmed |

### D: Recommendations, ranking, matching, issues

Two runs, merged.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| D-1 | bug | `services/matching/features.py:85` | `load_candidates` scores only RECOMMENDABLE; the 6 h stale sweep moves repositories to STALE and bumps `lifecycle_changed_at`, which triggers regeneration → `_persist` deletes their recommendations, which return later with new ids (or never, without app credentials). Breaks "ids survive regenerations"; saved items vanish. | fixed (recommendation-consistency) |
| D-2 | bug | `services/ranking/service.py:151` | `_persist` reads dismissals before locking Recommendation rows → a dismiss committing in between is missed → dismissed repository recreated. | fixed (recommendation-consistency) |
| D-3 | bug | `services/ranking/service.py:215` | Dismiss (cascade deletes children first) and persist (locks parent first) lock in opposite orders → deadlock; dismiss 500 or generation fails. | fixed (recommendation-consistency) |
| D-4 | bug | `services/ranking/service.py:159` | Persist locks Issue rows then deletes RecommendedIssue; issue refresh deletes RecommendedIssue then Issue → deadlock. | fixed (recommendation-consistency) |
| D-5 | bug | `services/ranking/freshness.py:45` | Restore reuses a running generation that already loaded candidates; freshness ignores dismissals and new pool members → restored or newly found repositories missing until an unrelated change. | fixed (recommendation-consistency) |
| D-6 | bug | `services/ranking/service.py:164` | Concurrently deleted issues are dropped from rows and snapshot, but score, signals, label and reason text ("3 open issues…") still count them → explanation not backed by stored data. | fixed (recommendation-consistency) |
| D-7 | gap | `services/ranking/explain.py:188` | Reasons emitted for signals > 0 even when weight 0 → explanations for signals scoring didn't use (FR-REC-003). Filter on contribution > 0. | partial |
| D-8 | bug | `services/ranking/score.py:99` | Relevance gate checks raw signal values, not weights → a weight-0 relevance signal still admits a candidate. | partial |
| D-9 | bug | `services/matching/issues.py:193` | Issue with only technologies the developer lacks still counts via approachability + difficulty (score 0.40 ≥ 0.3) → "matches your profile" for a Rust issue shown to a Python dev. | partial |
| D-10 | bug | `services/ranking/service.py:156` | Dismissals during a run removed after the `top_n` cut → fewer than N stored although next candidates exist. | fixed (recommendation-consistency) |
| D-11 | bug | `services/issues/classify.py:336` | Title keyword order puts docs, test and CI before bug → "[Bug]: docs build crashes" becomes documentation → beginner vote. Undoes the `[Bug]:` fix. | confirmed |
| D-12 | bug | `services/issues/classify.py:412` | `body_length` vote uses raw markdown (template HTML comments included) → wrong or unknown difficulty. | confirmed |
| D-13 | bug | `services/issues/labels.py:110` | `[Type] Bug`-style labels never normalized (`_EDGES` strips only `[`) → no category, filter misses, documentation vote lost. | confirmed |
| D-14 | bug | `services/ranking/freshness.py:34` | `due_profiles` requires candidates → profile with an emptied pool keeps old recommendations forever. | fixed (recommendation-consistency) |
| D-15 | gap | `recommendations/admin.py:25` | ScoringConfig editable once no Recommendation references it → past versions' numbers can change (feedback snapshots, baselines). Activate action doesn't validate (`stored=True`). | partial |
| D-16 | bug | `services/matching/issues.py:136` | Difficulty-fit part of an unknown-difficulty issue's score has no reason → unexplained score. | confirmed |
| D-17 | gap | `services/ranking/config.py:354` | Openness points not validated to sum ≤ 1; silently capped → saturated signal. | confirmed |
| D-18 | gap | `services/issues/classify.py:423` | `technology_count >= 2` and `MIN_VOTES = 2` hard-coded (rule: weights are config). | confirmed |
| D-19 | cleanup | `services/matching/issues.py:105` | `_join` copied three times; GOOD_FIRST_ISSUE/HELP_WANTED re-declared from `labels.py`. | confirmed |
| D-20 | cleanup | `services/ranking/score.py:65` | `weighted_score` used only by tests; `score_candidate` duplicates the formula. | confirmed |
| D-21 | perf | `services/ranking/freshness.py:43` | `due_profiles` loads every profile into Python every 30 min; express as SQL filter. | confirmed |

### E: Feedback, evaluation services, benchmark commands

Excludes what R-1, R-2, R-7, R-8, R-13 and R-14 already cover.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| E-1 | bug | `services/evaluation/baseline.py:333` | `write` replaces the whole dataset entry with only the configs evaluated in this run. `evaluate_ranking --write-baseline --config v2-deterministic` drops v1 from `benchmark-v1`; `test_baseline_metrics_unchanged` asserts both v1 and v2 are present → CI fails. Merge into the existing entry instead. | fixed (evaluation-tooling-integrity) |
| E-2 | bug | `recommendations/management/commands/evaluate_ranking.py:170` | `--write-baseline --min-score X` records the override as every config's `min_score` (and metrics at X), but the test re-evaluates without override at `baseline.MIN_SCORE` → permanent "Ranking changed" mismatch. Reject `--min-score` with `--write-baseline` (as `--config-file` is). | fixed (evaluation-tooling-integrity) |
| E-3 | gap | `services/evaluation/export.py:36` | Export claims anonymized output, but the pool includes `previously_interacted` candidates (repositories the user contributed to) by full name → a committed `benchmark-v2` lets anyone re-identify the developer from their contribution set. | fixed (privacy-deletion-finality) |
| E-4 | bug | `services/evaluation/export.py:36` | Export reuses `load_candidates`, which drops dismissed and non-RECOMMENDABLE (STALE, FETCHING, see D-1) repositories → the judged pool depends on when the beat sweep last ran and omits the user's clearest "not relevant" examples. | fixed (recommendation-consistency) |
| E-5 | bug | `services/feedback.py:86` | `save` does not check for a dismissal; a save from a second tab with a stale recommendation racing `dismiss` leaves a SavedRepository for a hidden repository (shown in Saved while hidden; `dismiss` deleted the save first). Lock or re-check `DismissedRepository` inside the transaction. | fixed (recommendation-consistency) |
| E-6 | bug | `services/feedback.py:117` | `dismiss` deletes the SavedRepository without recording an `unsaved` event → the append-only event log shows the repository as still saved; save analytics overcount. | fixed (recommendation-consistency) |
| E-7 | bug | `services/feedback.py:73` | `viewed` de-duplication is check-then-insert without a lock → two concurrent views (StrictMode double effect, two tabs) both store an event. | fixed (recommendation-consistency) |
| E-8 | bug | `recommendations/management/commands/evaluate_ranking.py:183` | `--json` writes without creating the parent folder or catching `OSError` → raw traceback for `--json ../../judging/new/report.json`; the other commands create output folders (CLAUDE.md §7). | fixed (evaluation-tooling-integrity) |
| E-9 | bug | `services/evaluation/sheet.py:155` | `_languages` sums byte counts, but the dataset format allows `null` bytes (`_count`) → `TypeError` in `benchmark_sheet`, not caught (only OSError/ValueError/KeyError/SheetError) → traceback. | fixed (evaluation-tooling-integrity) |
| E-10 | perf | `feedback/api.py:252` | Saved list prefetches every snapshot of each repository (up to `REPO_SNAPSHOT_HISTORY`) to read only the newest. | confirmed |

### F: Frontend (`apps/frontend/src`)

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| F-1 | bug | `features/sync/api.ts:24` | `useSyncStatus` invalidates every `['profile']` query on each status fetch whose latest job is COMPLETED, which is the steady state. Window focus or remounting `/app` (back from a detail page) refetches skills, interests, repositories, recommendations, discovery and saved lists every time, and can refetch the list mid-dismiss so the card flickers back. Invalidate only when the job id or status changes, as `useRecommendationStatus` does. | fixed (frontend-correctness) |
| F-2 | bug | `features/feedback/api.ts:259` | Saved and hidden lists fetch one page of `page_size=100` with no pagination → a user with more than 100 saved or hidden projects silently cannot see or restore the rest. | fixed (frontend-correctness) |
| F-3 | bug | `features/recommendations/RecommendationList.tsx:134` | `?page=N` past the last page (after dismissals or a regeneration shrinks the list, or a shared link) gets a DRF 404 → "Could not load recommendations. Please refresh the page."; refreshing keeps the page in the URL, so it never recovers. Dismissing the only card on the last page shows the empty-state text although earlier pages exist. | fixed (frontend-correctness) |
| F-4 | bug | `features/feedback/RecommendationActions.tsx:287` | Save button is not disabled while pending; a fast double click sends POST and DELETE concurrently with no ordering guarantee, and the first mutation's rollback restores a snapshot taken before the second → UI shows Saved while the server has it unsaved (or the reverse). | fixed (recommendation-consistency) |
| F-5 | bug | `features/recommendations/RecommendationCard.tsx:332` | "N relevant issues" links to `#relevant-issues`, but client-side navigation does not scroll to hashes and the target renders only after the detail query loads → user lands at the top of the page. | fixed (frontend-correctness) |
| F-6 | bug | `features/recommendations/RecommendationDetailPage.tsx:98` | Non-numeric or zero `:id` (also `IssueDetailPage.tsx:33`) disables the query, so `isPending` stays true → "Loading…" forever instead of a not-found message. | fixed (frontend-correctness) |
| F-7 | bug | `features/auth/RequireAuth.tsx:245` | Only `/auth/me` 401s redirect; with `staleTime` 60 s an expired session shows "Could not load ... Please refresh the page" on every panel instead of returning to sign-in. Handle 401 globally (QueryCache `onError`). | fixed (frontend-correctness) |
| F-8 | bug | `features/recommendations/RecommendationList.tsx:61` | `closeUndo` depends on `location`, so any filter change (new location) re-runs the `DismissUndo` effect and restarts the 10 s Undo timer. | fixed (frontend-correctness) |
| F-9 | perf | `features/recommendations/api.ts:235` | The invalidation effect runs in every observer of `useRecommendationStatus`, including the passive one in `usePipelineStage` → two invalidations per finished generation; the second cancels the first list fetch and restarts it. | fixed (frontend-correctness) |

### G: Scripts, compose, CI, Dockerfiles, `.env.example`

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| G-1 | bug | `scripts/stop.mjs:151` | Node runners match `scripts/(start\|backend\|worker\|beat\|redis).mjs` without checking the repository path (their command lines are relative) → `npm run stop` kills `node scripts/start.mjs` and friends of any other project on the machine. CLAUDE.md §6 promises "kills this repo's stack only". Check the process's cwd or pass a marker (`CF_STACK_PID`/repo path) on the runner command line. | confirmed |
| G-2 | bug | `scripts/redis.mjs:81` | No SIGHUP handler; closing the console ends the runner without killing the detached `wsl.exe sleep infinity`, and `npm run stop` never matches `wsl.exe` → the distro and Redis stay awake indefinitely. | confirmed |
| G-3 | bug | `scripts/child.mjs:58` | POSIX `process.kill(-child.pid, signal)` throws ESRCH if the group already exited → uncaught exception inside the signal handler, and the `killTree` fallback is never scheduled. Spawn `error` (bad `UV_BIN` path) is also unhandled → crash with a stack trace instead of a message. | partial |
| G-4 | bug | `scripts/wait-port.mjs:128` | `net.connect` has no timeout; against a host that drops packets (remote `REDIS_URL`, firewalled WSL IP) one attempt waits the OS TCP timeout (21 s to 2 min) → the documented `timeoutMs` deadline is overshot several times over. | partial |
| G-5 | gap | `docker-compose.yml:68` | Frontend service loads the whole `.env` (`GITHUB_CLIENT_SECRET`, `TOKEN_ENCRYPTION_KEYS`, `DJANGO_SECRET_KEY`) though it needs only `VITE_*` → secrets present in the frontend container's environment, contrary to the least-exposure rule for secrets (CLAUDE.md §3). | fixed (security-hardening) |
| G-6 | bug | `docker-compose.yml:43` | Redis published on host port 6379 (all interfaces, no auth) collides with the WSL Redis that `npm start` uses on this machine and exposes the broker to the LAN. Bind `127.0.0.1:` or drop the port mapping. | fixed (security-hardening) |
| G-7 | bug | `scripts/beat.mjs:146` | Beat schedule file has a fixed name in the OS temp dir → two checkouts (or a worktree) share and overwrite one schedule state file. Include a hash of `root`. | confirmed |
| G-8 | gap | `.github/workflows/ci.yml:88` | `cancel-in-progress: true` also applies to pushes to `main` → a quick second push cancels the first commit's run, so a broken commit on `main` can go unchecked. Limit cancellation to pull requests. | partial |
| G-9 | gap | `scripts/check-version.mjs:170` | Checks only the top-level `version` of each `package-lock.json`, not `packages[""].version`, which `npm ci` also compares → a half-updated lock passes the check. | partial |
| G-10 | cleanup | `scripts/setup.mjs:35` | Setup runs `npm install` in `apps/frontend` (can rewrite the lockfile) where CI uses `npm ci` → a local setup can leave an uncommitted lockfile diff that CI does not reproduce. | confirmed |

### H: Platform, settings, migrations, remaining frontend, test gaps

Paths under `apps/backend/` unless they start with `apps/frontend/`. `makemigrations --check` is clean.
H-2 and H-4 confirmed by the reviewer (DRF `get_ident` source; `redact()` probes).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| H-1 | bug | `config/settings/base.py:157` | DRF throttles count in the Redis cache → Redis down = every API request (health included) 500s after the 5 s socket timeout, twice per request. Breaks "reads come from PostgreSQL" and degrade-gracefully. Tests use LocMemCache, so it's never exercised. | fixed (github-error-resilience) |
| H-2 | bug | `config/settings/base.py:148` | `NUM_PROXIES` unset → DRF keys throttles on raw `X-Forwarded-For` → a random XFF per request bypasses anon (60/min) and auth (10/min) limits. | fixed (security-hardening) |
| H-3 | bug | `core/logging.py:41` | `RedactSecretsFilter` calls `record.getMessage()` outside logging's error guard → a bad log call (missing arg) raises into the caller, crashing a task step or turning a handled error into a 500. | fixed (security-hardening) |
| H-4 | gap | `core/logging.py:15` | Redaction misses `key='value'` reprs, `'state'` in dict/JSON, and `Authorization: token <non-gh>` → client secret or OAuth state can reach logs. Tests cover only unquoted and `gh*_` cases. | fixed (security-hardening) |
| H-5 | bug | `apps/frontend/src/main.tsx:9` | Production QueryClient keeps default `retry: 3` for 4xx → normal `404 not_analyzed` shows "Loading…" about 7 s over 4 requests; 401s and 429s retried too. Tests set `retry: false`, which hides it. | fixed (frontend-correctness) |
| H-6 | gap | `config/settings/production.py:7` | System checks (token keys, weights) never run under gunicorn or the Celery worker → misconfigured deploy starts and fails per request (empty `TOKEN_ENCRYPTION_KEYS` → 500 on sign-in). | fixed (security-hardening) |
| H-7 | gap | `core/checks.py:52` | No checks for `EXPERIENCE_THRESHOLDS`, `SYNC_MAX_ATTEMPTS`, `SYNC_STALE_AFTER_SECONDS`, `JOB_RECOVERY_INTERVAL_SECONDS`, GitHub caps, etc. → e.g. interval 0 = `recover_stale_jobs` hot loop; scalar threshold = every analysis fails. | confirmed |
| H-8 | gap | `apps/frontend/src/routes/PrivacyPage.tsx:15` | Says the GitHub identifier is kept until disconnect, but `User.username = gh_<github_id>` survives disconnect. | fixed (privacy-deletion-finality) |
| H-9 | gap | `apps/frontend/src/routes/PrivacyPage.tsx:11` | "What we store" omits SyncJob history, candidates and search queries, `AuditEvent.ip_hash` (kept after account deletion), session rows. | fixed (privacy-deletion-finality) |
| H-10 | bug | `recommendations/migrations/0003_seed_v2_deterministic.py:59` | v2 seed deactivates whatever config is active, not just v1 → an operator-chosen config silently replaced by v2 on upgrade. | confirmed |
| H-11 | bug | `recommendations/migrations/0002_seed_v1_deterministic.py:40` | Re-applying 0002 after unseed checks `exists(active)` including v1 itself → v1 deactivated, no active config, generation fails. Unseed paths untested. | confirmed |
| H-12 | gap | `config/celery.py:5` | Celery and `manage.py` default to development settings, `wsgi.py` to production → with the variable unset, worker and beat run `DEBUG=True` without the `REDIS_URL` guard. | fixed (security-hardening) |
| H-13 | gap | `config/urls.py:25` | Only `handler404`/`handler500` set → Django-level 400/403 (DisallowedHost, RequestDataTooBig, PermissionDenied) return HTML, breaking the error envelope. | fixed (security-hardening) |
| H-14 | bug | `core/api.py:11` | `HealthView` is throttled (60/min per IP) → load balancer probes get 429 and mark a healthy instance down. | fixed (security-hardening) |
| H-15 | bug | `config/settings/production.py:13` | `SECURE_SSL_REDIRECT` without health exemption → plain-HTTP probes get 301. `SECURE_PROXY_SSL_HEADER` trusted unconditionally. | fixed (security-hardening) |
| H-16 | gap | `config/settings/production.py:15` | HSTS `includeSubDomains` + `preload` hard-coded, 1-year max-age → irreversible on a shared parent domain. Make opt-in. | fixed (security-hardening) |
| H-17 | bug | `apps/frontend/src/features/profile/languages.ts:13` | "Other" summed from shares pre-rounded to 2 decimals → many small languages become 0, "Other" disappears, rows show "0%". | fixed (frontend-correctness) |
| H-18 | gap | `apps/frontend/package.json:1` | No Playwright config, specs or CI job despite CLAUDE.md §4; OAuth → onboarding → dashboard, dismiss/undo, delete flows covered only by mocked unit tests. | fixed (frontend-correctness) |
| H-19 | gap | `tests/test_api_platform.py:82` | No tests for: failing cache backend, migration unseed, malformed log call or quoted redaction, Django-level 400, privacy page vs `data_deletion`. | confirmed |
| H-20 | perf | `config/settings/base.py:182` | `CELERY_RESULT_BACKEND` stores every task result in Redis, never read. Set `CELERY_TASK_IGNORE_RESULT`. | confirmed |

### Not yet reviewed

Nothing major. Every area has had one unverified review pass.

### Cross-cutting themes

1. **No ownership fencing** for claims (B-2, B-10, C-3, C-4, C-19): one claim-token mechanism fixes jobs and repositories.
2. **Deletion not final** (A-1, B-4): running work must re-check existence or cancellation before writing.
3. **Lock ordering and deadlocks** (B-3, C-7, D-3, D-4, A-10).
4. **GitHub status mapping** (A-2, A-3, A-4, A-5, C-1, C-6): 301, secondary 403 and 451 are mis-classified, so one repository fails a whole job.
5. **Stale ≠ gone** (D-1, D-14, C-8, E-4): staleness changes what users see and what gets exported.
6. **Baseline tooling** (R-1, R-2, E-1, E-2): `--write-baseline` can write a baseline CI then rejects. Fix together in `baseline.py` + `evaluate_ranking`, before K-1.
7. **Save/dismiss consistency** (D-2, D-3, D-10, E-5, E-6, F-4): one lock order and one "is dismissed" check for save, dismiss and persist.
8. **Privacy of deleted or exported data** (A-7, A-8, E-3, G-5): GitHub identity survives deletion; benchmark export re-identifiable. **Settle E-3 before committing benchmark-v2.**
9. **Frontend cache churn** (F-1, F-9, H-5): invalidate on job transitions only; no retry on 4xx.
10. **Redis as hidden hard dependency** (H-1, H-14, H-20, A-16): throttles and results make Redis required for plain reads.
11. **Production hardening** (H-2, H-6, H-12, H-13, H-15, H-16, G-5, G-6): settings drift between tiers, spoofable client IP, unchecked config.
12. **Secrets in logs** (H-3, H-4): redaction gaps plus a filter that can crash its caller.

## Summary

Status after verification: `confirmed` = defect exists as described; `partial` = defect exists but
scenario or severity is narrower; `false-positive` = not a defect.

| Section | Rows | Confirmed | Partial | False positive |
|---|---|---|---|---|
| K (known) | 5 | — | — | — |
| DOC | 2 | — | — | — |
| R last-commit review | 14 | 12 | 2 | 0 |
| A auth/GitHub | 20 | 16 | 3 | 1 |
| B jobs/profiling | 20 | 15 | 5 | 0 |
| C repositories/discovery | 23 | 19 | 4 | 0 |
| D recommendations/issues | 21 | 15 | 6 | 0 |
| E feedback/evaluation | 10 | 8 | 2 | 0 |
| F frontend | 9 | 8 | 1 | 0 |
| G scripts/infra | 10 | 6 | 4 | 0 |
| H platform/settings/tests | 20 | 16 | 4 | 0 |
| V batch 5 review | 9 | 6 | 2 | 1 |
| W batch 6 review | 10 | 10 | 0 | 0 |
| X batch 7 review | 12 | 11 | 0 | 1 |
| Y batch 9 review | 10 | 9 | 1 | 0 |
| **Total** | **195** | **151** | **34** | **3** |

## Verification notes

**False positive**
- A-10: `update_or_create` goes through `get_or_create`, which catches the IntegrityError and re-gets on `github_id`. Only a full_name clash with a different github_id still raises (a rename race, already covered by C-2).

**Partial: real defect, narrower scope**
- A-4: dropped contribution evidence is real. The languages step only fails if a rename happens between listing and the languages call.
- A-11: needs this user's repository renamed away and the name re-created mid-sync. Not permanent: the next sync re-plans.
- A-12: other sessions see only an unconnected, empty account. Low severity.
- B-4: recreation only succeeds when all evidence is README-only or on surviving shared repositories (deferred FKs abort otherwise).
- B-7: stale jobs are requeued by recovery, so the user does get re-analyzed. Only the "already active" report is misleading.
- B-8: millisecond window. The `.first()`→None half is harmless because callers ignore the return value.
- B-10: needs beat down, or a redelivery that lands before recovery.
- B-11: a cancel with a live worker self-heals. Only dead-worker jobs keep a spinner.
- C-3, C-4, C-19: only reachable when an analysis takes more than 10 min (pathological latency).
- C-5: needs a queued readme task to run after the repository was marked FAILED (race).
- D-1: saved items do **not** vanish (the Saved list is keyed on repository). The rest holds: recommendations drop out on the hourly stale sweep and come back with new ids, or never without app credentials.
- D-7, D-8: latent. Reachable only with a config that gives a weight of 0; no seeded config does.
- D-9: spec-mandated (issue-matching spec: "technology match or an approachability label"). The real defect is the wording "matches your profile".
- D-14: discovery's pool-step completion starts a generation that empties the list. Stuck only when D-5 reuse or a failed generation interferes.
- D-15: the edit part holds; activation already re-validates, so an invalid config fails loudly.
- E-5: a concurrent race rolls back with a 500 (FK), no orphan. The orphan window is two lines wide.
- E-9: exports never hold null bytes. Needs a hand-made `--export`.
- F-7: the redirect happens on the next `/auth/me` refetch (after 60 s stale, on focus or mount), not never.
- G-3: the ESRCH race is narrow; the spawn-error half is unreachable (`uv.mjs` probes candidates).
- G-4: overshoot is one OS connect timeout (about 21 s on Windows), not "several times over".
- G-8: the surviving run tests the tip, which includes the earlier commit. Only per-commit attribution is lost.
- G-9: the gap is real, but `npm ci` doesn't compare the root version.
- H-6: `migrate` runs system checks, so a deploy that migrates first catches them.
- H-13: only the 400 part holds; DRF already turns PermissionDenied into the envelope.
- H-14: normal probe rates (every 5–30 s) stay under 60/min.
- H-16: max-age is configurable (0 disables); preload does nothing until the domain is submitted.
- R-10: documented design ("a query is planned in all bands or not at all"); waste is at most bands−1 requests.
- R-12: refreshes re-run `eligibility()` within hours (6 h issues staleness), unless app credentials are missing.

**Worse than reported**
- B-13: repository analysis re-raises any exception, so one deeply nested manifest in a discovered repository fails every discovery run that touches it, for every user.

**Corrected locations** (cited lines were stale)
- R-14 `services/evaluation/export.py:80` + `sheet.py:118`; E-1 `baseline.py:32-41`; E-10 `feedback/api.py:119-123`.
- C-3 `lifecycle.py:46-95`; C-9 `repositories/tasks.py:111`; C-15 `tasks.py:71-90`; C-16 `tasks.py:40-92`; C-22 `lifecycle.py:76-78`.
- D-11 `classify.py:38-46`; D-12 `classify.py:114`; D-17 `config.py:171`; D-18 `classify.py:65,125`.
- G-1 `scripts/stop.mjs:10,43`; G-2 `redis.mjs:60-62`; G-4 `wait-port.mjs:10,17`; G-7 `beat.mjs:22`; G-8 `ci.yml:8-10`.
- H-11 `0002_seed_v1_deterministic.py:40,46`; H-13 `urls.py:55-56`.

**Found during verification, not yet rows**
- G-6 extra: Postgres published on `5433` with password `contribfinder` in compose.
- H-1 extra: `cached_db` sessions also hit Redis. Fixed with H-1 (sessions now use the database backend).
- G-10 extra: `uv sync` in setup is not `--frozen` either.

## Fix batches

Each batch fits one OpenSpec change. Order = suggested priority. Partial rows are included but
can be deprioritized. Every verified row is in exactly one batch (A-10 dropped).

| # | Batch | Rows | Why together |
|---|---|---|---|
| 1 | **Security hardening** | H-2, H-4, H-3, H-12, H-15, H-16, H-6, H-13, H-14, G-5, G-6, A-15 | Spoofable throttle IP, secrets in logs, settings drift between tiers, deploy defaults. Small, isolated, high value. |
| 2 | **Privacy and deletion finality** | A-1, B-4, A-7, A-8, A-9, A-12, H-8, H-9, E-3, A-19 | "Delete" must mean deleted: running work re-checks before writing; identity leftovers; privacy page matches reality; export anonymization. **E-3 before committing benchmark-v2.** |
| 3 | **Evaluation tooling** | R-1, R-2, E-1, E-2, R-7, R-8, R-13, R-14, E-8, E-9 | `--write-baseline` and sheet import must be trustworthy before K-1 (judging real-a-v2). Offline only, low risk. |
| 4 | **Job lifecycle and claim fencing** | B-1, B-2, B-3, B-5, B-7, B-8, B-9, B-10, B-11, B-12, B-18, B-19, C-3, C-4, C-10, C-19 | One claim-token mechanism for jobs and repositories; zombie PENDING jobs (B-1); one `_start_job` helper; ordered catalog upsert. |
| 5 | **GitHub error handling and resilience** | A-2, A-3, A-4, A-5, A-6, A-11, A-13, A-14, B-13, C-1, C-6, C-9, H-1 | Classify 301, secondary 403, 451 and decryption errors correctly; one bad repository or manifest never fails a whole job; a Redis outage never breaks reads. |
| 6 | **Recommendation consistency** | D-1, D-2, D-3, D-4, D-5, D-6, D-10, D-14, E-4, E-5, E-6, E-7, F-4 | Stale ≠ gone; one lock order and one dismissal check for save, dismiss and persist; freshness sees restores and new candidates. |
| 7 | **Discovery and repository data** | C-2, C-5, C-7, C-8, C-11, C-12, C-13, C-14, C-15, C-16, C-17, C-18, R-3, R-4, R-5, R-6, R-9, R-10, R-11, R-12 | Eligibility re-check via lifecycle, provenance pruning, not_code false positives, search upsert side effects, one shared ordering helper. |
| 8 | **Signal and explanation accuracy** | B-6, B-14, B-15, B-16, D-7, D-8, D-9, D-11, D-12, D-13, D-15, D-16, D-17, D-18 | Wrong experience level, missed README badges, misclassified issues, reasons not backed by scoring. Ranking-visible: evaluate on the benchmark. |
| 9 | **Frontend correctness** | F-1, F-2, F-3, F-5, F-6, F-7, F-8, F-9, H-5, H-17, H-18 | Query invalidation churn, no 4xx retry, pagination gaps, 401 handling; add Playwright for the main flows. |
| 10 | **Dev scripts, checks and migrations** | G-1, G-2, G-3, G-4, G-7, G-8, G-9, G-10, H-7, H-10, H-11, H-19, H-20 | `npm run stop` kills only this repo; config checks for unchecked settings; safe seed migrations; tests for those paths. |
| 11 | **Performance and cleanup** | A-16, A-17, A-18, A-20, B-17, B-20, C-20, C-21, C-22, C-23, D-19, D-20, D-21, E-10, DOC-1, DOC-2, X-11, X-12, Y-9, Y-10 | No behavior change; do alongside nearby batches or as one sweep. C-22 already fixed in batch 4. |
| 12 | **Batch 5 follow-ups** | V-1, V-2, V-3, V-4, V-5, V-6, V-7, V-8, V-9 | Review of `github-error-resilience`. Fixed in the same release (0.12.5); V-1 and V-3 replace design decisions D7 (client raises `GitHubInvalidResponse`) and D9 (in-memory throttle fallback instead of fail-open). |
| 13 | **Batch 7 follow-ups** | X-1…X-10 | Review of `discovery-repository-data`. X-1…X-6 fixed in the same release (0.12.7); X-7…X-9 accepted, X-10 false positive. X-11 and X-12 went to batch 11. |
| 14 | **Batch 9 follow-ups** | Y-1…Y-10 | Review of `frontend-correctness`. Y-1…Y-5 and Y-8 fixed in the same release (0.12.8); Y-6 and Y-7 open (next frontend change); Y-9 and Y-10 went to batch 11. |

Shipped: batch 1 in 0.12.1, 2 in 0.12.2, 3 in 0.12.3, 4 in 0.12.4, 5 and 12 in 0.12.5, 6 (with
W-1…W-10) in 0.12.6, 7 and 13 in 0.12.7, 9 and 14 in 0.12.8. Next: batch 10 (dev scripts, checks and
migrations); batch 8 (signal and explanation accuracy) is ranking-visible and waits for K-1.

Not in a batch: K-1…K-5 (roadmap items, tracked elsewhere). K-1 depends on batches 2 (E-3) and 3.
