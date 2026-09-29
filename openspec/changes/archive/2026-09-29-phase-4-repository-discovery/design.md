## Context

v0.3.0 state that this phase builds on:
- `Repository` is already shared (unique `github_id`/`full_name`) with `RepositoryLanguage`, `RepositoryTopic` and `RepositoryDependency`. The storage helpers `_upsert_repository`, `_replace_languages`, `_replace_topics` and `_read_manifests` are private to `services/github/sync.py`.
- `UserRepository` links owners and contributors. Contributor links are the source for `previously_interacted`.
- `DeveloperProfile` → `DeveloperSkill` (+ `SkillEvidence`, source per row) and `DeveloperInterest`. The catalog exposes `SKILLS_BY_SLUG`, `INTERESTS_BY_SLUG`, skill topics and linguist names.
- `GitHubClient` handles pagination, ETags (cache key scoped by `cache_scope`), rate-limit mapping and typed errors. It only authenticates with a user's Bearer token.
- `SyncJob` is per user with a one-active-per-(user, type) constraint. `claim_job`/`finish_job` are shared. `decide_retry` maps errors to `Retry`/`Fail(code)`. The retry loop lives inside `github.tasks.sync_github_profile`. `cancel_active_syncs` already cancels every job type, but `active_jobs`/`_expire_stale` only look at syncs.
- There is no Celery beat locally: `npm start` runs Django, Vite, WSL Redis and a thread-pool worker (`--pool=threads`, `CELERY_CONCURRENCY` 4; prefork does not run on Windows). Docker Compose has a `beat` service.

Requirements are in `specs/repository-discovery`, `specs/repository-analysis`, `specs/repository-activity` and the `sync-jobs` delta. Motivation is in `proposal.md`.

## Goals / Non-Goals

**Goals:**
- Each stage (query generation → search → pre-filter → analysis → activity → eligibility → pool maintenance) is a separately testable unit. Query generation, filters, activity and staleness are pure functions with no database or HTTP.
- Repository work is shared and idempotent: a fresh repository is never fetched twice, and concurrent runs never analyze the same repository at once.
- Everything Phase 5 needs is stored relationally and queryable: pool membership, provenance, eligibility, community flags, labels, latest snapshot.

**Non-Goals:**
- Ranking, scores, match labels or recommendation UI (Phase 5).
- Issue ingestion, issue activity and issue response times (Phase 7). `open_issues` comes from the repository payload only.
- The `similar_repo` strategy: the source value exists for Phase 5+, but no generator is built.
- Semantic search and the EMBEDDED lifecycle state (Phase 6).
- Dismissed-repository exclusion (Phase 8a). The pool has no per-developer exclusion list yet.
- Manifests below the repository root, as in Phase 3.

## Decisions

### D1. Data model (`repositories` app)
**`Repository` gains:**
- `lifecycle` (TextChoices: discovered, fetching, analyzed, indexed, recommendable, stale, refreshing, failed; default `discovered`, indexed), `lifecycle_changed_at`, `lifecycle_error` (≤ 50, code only).
- `stale_parts` (JSON list of data types) and `previous_lifecycle` (to restore after a transient failure or cancel).
- `is_eligible` (bool, null = never assessed), `ineligible_reason` (≤ 50).
- Community fields: `has_contributing`, `has_code_of_conduct`, `has_issue_templates`, `has_pull_request_template`, `has_good_first_issue_label`, `has_help_wanted_label` (nullable bools; null = not fetched yet).
- Per-data-type timestamps: `synced_at` (existing, now "metadata"), `readme_synced_at`, `community_synced_at` (community files and labels), `dependencies_synced_at`, `activity_synced_at`.
- A partial index on `lifecycle` for the backlog query.

Existing rows get `lifecycle=discovered`. The backlog only processes repositories that are in a pool, so owned repositories are never refreshed by it.

**`RepositoryReadme`** (1:1 Repository, CASCADE): `content` (text, truncated to `REPO_README_MAX_BYTES`), `size` (the original size), `truncated`, `fetched_at`. No row with `readme_synced_at` set means "no README". It is a separate table so that list queries on `Repository` never load README text.

**`RepositorySnapshot`** (FK Repository, CASCADE, ordered `-captured_at`): `captured_at`, `stars`, `forks`, `open_issues`, `days_since_push`, `commits_90d` (null = unknown), `prs_opened_90d`, `prs_merged_90d`, `prs_sample_capped` (bool), `contributors` (null = unknown), `latest_release_at` (null), `activity_label`, `thresholds_version` (a hash of the thresholds used). History is trimmed to `REPO_SNAPSHOT_HISTORY` after each insert.

**`RepositoryCandidate`**: `developer` (FK `DeveloperProfile`, CASCADE), `repository` (FK, CASCADE), `first_discovered_at`, `last_seen_at`; unique (developer, repository); index (developer, -last_seen_at).

**`CandidateDiscovery`**: `candidate` (FK, CASCADE), `source` (language_search | topic_search | skill_search | interest_search | similar_repo | previously_interacted), `query` (≤ 256: the query without its qualifiers, e.g. `language:Python`, so the day-granular `pushed:>=` date never creates a second record for the same query; blank for previously_interacted), `search_rank` (null for previously_interacted), `first_seen_at`, `last_seen_at`; unique (candidate, source, query).

- **Deviation from the CLAUDE.md sketch** (`RepositoryCandidate(developer, repository, source, query, discovered_at)`): a repository found by several queries would then be several candidates, and every "is it in the pool" or per-candidate query would need `DISTINCT`. The split keeps one candidate per (developer, repository) and still records every source.
- **Why FK to `DeveloperProfile`, not `User`:** the profile row is upserted (stable pk), and deleting GitHub-derived data (FR-DATA-003) deletes the profile, so candidates cascade with it.
- **Eligibility on `Repository`, not on the candidate:** every eligibility rule is repository-level. A per-developer rule (the user's own repositories) is applied before insertion, so no candidate row carries it.

### D2. GitHub client additions (`services/github/client.py`)
- **Auth abstraction:**
  - The constructor takes an `auth_header` value instead of a raw token.
  - `for_user(user)` builds `Bearer <token>`.
  - New `for_app()` builds `Basic base64(client_id:client_secret)` with `cache_scope="app"` and raises `GitHubAuthError` if the credentials are unset.
  - `__repr__` stays secret-free.
  - A `cache_scope` override lets the user's discovery client use `"public"` for repository endpoints, so ETags for public repository data are shared between users and the app client. Search stays user-scoped.
- **New methods**, all returning normalized dataclasses:
  - `search_repositories(q, limit) -> list[GitHubRepo]`: one `GET /search/repositories?q=&per_page=limit` (limit ≤ 100). A 422 raises `GitHubValidationError`.
  - `get_community_profile(full_name) -> CommunityProfile(has_contributing, has_code_of_conduct, has_issue_template, has_pull_request_template, has_readme)` via `GET /repos/{r}/community/profile`.
  - `list_label_names(full_name) -> list[str]`: labels, at most 3 pages. The label check normalizes case, spaces and dashes (`good first issue`, `good-first-issue`, `help wanted`).
  - `get_readme(full_name) -> str | None`: raw; 404 → `None`.
  - `count_commits_since(full_name, since) -> int`: `per_page=1`; the count is the page number of the `rel="last"` link, else the item count. 409 (empty repository) → 0.
  - `count_contributors(full_name) -> int | None`: `per_page=1&anon=1`, same Link trick. A 403 "too large" or 204 → `None`.
  - `recent_pull_requests(full_name) -> PullSample(opened_90d, merged_90d, capped)`: one page, `state=all&sort=updated&direction=desc&per_page=100`.
  - `get_latest_release_date(full_name) -> datetime | None`: 404 → `None`.
- **`since` normalization:** `since` is truncated to the UTC date, so the URL, and therefore its ETag, is stable within a day.
- **Alternative:** the GraphQL API, which fetches all of this in 1–2 calls per repository. Rejected for now: it needs a second transport, error mapping and its own rate-limit (points) accounting. REST plus ETags reuses everything already tested. It can be revisited if per-repository request counts become the bottleneck.

### D3. Query generation (`services/discovery/queries.py`, pure)
- **Input:** `DiscoveryInput`, a snapshot of the developer's skills (slug, category, confidence, evidence sources), interests (slug, strength), owned non-fork repository topics, login, and `now`.
- **Output:** an ordered `list[PlannedQuery(source, q, key)]`, where `key` is a stable id for resume.
- **Strategies:**
  - **language_search**: top language skills by confidence, markup (HTML/CSS) excluded → `language:"<linguist name>"`.
  - **skill_search**: top framework/library/database/tool skills that have a catalog topic → `topic:<topic>`, plus `language:` of the developer's top language when that skill's ecosystem is tied to one (e.g. Django → Python). Otherwise topic only.
  - **interest_search**: top interests → `topic:<first interest topic> language:<top language>`. A second query, without language, is added only if budget remains.
  - **topic_search**: owned-repository topics used in ≥ 2 repositories that map to no skill or interest query → `topic:<t>`.
- **Qualifying skills:** confidence ≥ `DISCOVERY_MIN_SKILL_CONFIDENCE` (0.3) and at least one evidence source other than `readme`.
- **Qualifiers appended** to every query: `archived:false fork:false is:public pushed:>=<now − DISCOVERY_MAX_PUSH_AGE_DAYS> stars:>=<DISCOVERY_MIN_STARS> -user:<login>`. The date is day-granular, so queries are stable within a day.
- **Budget:** `DISCOVERY_MAX_QUERIES` (10) split by `DISCOVERY_QUERY_SHARES` (`{"language": 2, "skill": 4, "interest": 3, "topic": 1}`), in the fixed order language → skill → interest → topic. Unused slots carry forward to later strategies, then wrap around once to earlier ones. Identical `q` strings are deduplicated.
- **Alternative:** one combined query (`language:python topic:django topic:cli`). Rejected: GitHub ANDs topics, so combined queries return few results and lose per-source provenance.

### D4. Filters (`services/discovery/filters.py`, pure)
- `prefilter(repo: GitHubRepo, ctx) -> str | None` returns the reason code: `archived`, `fork`, `inactive` (push age), `no_license`, `few_stars`, `own_repository`. Stars are not checked for `previously_interacted`.
- `eligibility(repo: Repository, now, cfg) -> str | None` applies the same repository-level rules (no stars, no ownership) plus `repository_unavailable` for FAILED repositories.
- **License:** `license_spdx` non-empty. `NOASSERTION` ("Other") counts as licensed: GitHub found a license file it could not classify, so that is a presence signal, not a legal judgment.
- Search qualifiers already exclude most rejects. The prefilter still runs because qualifiers are not guaranteed (for example, a push between indexing and query), and because it counts reasons.

### D5. Repository analysis (`services/repositories/analysis.py`)
`RepositoryAnalysisService(client, now).analyze(repo, parts)`, where `parts ⊆ {metadata, readme, community, dependencies, activity}`. Everything is fetched first, then written in one transaction per repository:
- **metadata:** `get_repository` → shared `upsert_repository` + `replace_languages` + `replace_topics`. The helpers move from `services/github/sync.py` into `services/github/storage.py`; sync imports them from there. A repository that was never analyzed (`activity_synced_at` null) needs every part, including metadata: a search payload carries no languages. The one extra request is accepted rather than tracking languages freshness separately.
- **readme:** `get_readme`, then upsert or delete `RepositoryReadme`.
- **community:** `get_community_profile` + `list_label_names`.
- **dependencies:** `read_manifests` (moved) → replace `RepositoryDependency`.
- **activity:** the D6 fetches → `compute_activity` → insert the snapshot and trim the history.

**Lifecycle** (`services/repositories/lifecycle.py`):
- `claim(repo_id) -> bool` is a conditional `UPDATE`:
  - from `discovered | stale | failed` (and `fetching | refreshing` older than `SYNC_STALE_AFTER_SECONDS`);
  - to `fetching`, or to `refreshing` if the repository had been analyzed before;
  - storing `previous_lifecycle`.
- Success walks `analyzed → indexed` inside the write transaction, runs `eligibility`, and ends at `recommendable` or `indexed`. The intermediate states are visible only to concurrent readers; the transitions are recorded for correctness and tests, not for UI.
- **Errors:**
  - `GitHubNotFound` / `GitHubForbidden` (not a rate limit) / 451 (mapped to `GitHubClientError`) → `failed` with `lifecycle_error ∈ {not_found, forbidden, unavailable}`.
  - `GitHubRateLimited`, `GitHubTransientError`, `GitHubAuthError` and `JobCancelled` → `release(repo)`, which restores `previous_lifecycle`, then re-raise.
  - A 404 from an optional endpoint (README, release, community) is data, not an error.
- **Tasks** (`repositories/tasks.py`, thin): `sync_repository(repo_id)` (all stale or missing parts, app client), and `sync_repository_readme(repo_id)` (README only, used when `stale_parts == ["readme"]`). Both claim the repository, and both return without error if the claim fails.

### D6. Activity (`services/matching/activity.py`, pure)
- `ActivityData` (raw fetch results, `None` = unknown) → `compute_activity(data, pushed_at, now, thresholds) -> ActivitySignals` (the snapshot fields plus the label).
- **Fetches:** `count_commits_since(now − 90d)`, `recent_pull_requests`, `count_contributors`, `get_latest_release_date`: 4 requests. A `GitHubForbidden` on contributors → `None`.
- **Thresholds** come from the `ACTIVITY_THRESHOLDS` setting (`recent_push_days=30`, `recent_commits=10`, `recent_merged_prs=5`, `moderate_push_days=90`, `moderate_commits=1`, `moderate_merged_prs=1`) and implement the spec rules.
- `thresholds_version` is a short hash of the thresholds JSON, so a label can be traced to the configuration that produced it.
- **Alternative:** a numeric activity score now. Deferred: Phase 5's `activity_signal` calculator derives its 0..1 score from these stored signals, keeping scoring out of discovery.

### D7. Discovery service and job (`services/discovery/service.py`)
- `SyncJob.JobType.REPOSITORY_DISCOVERY`, steps `queries → search → interactions → analysis → pool`. `STEPS_BY_JOB_TYPE` gains it.
- **Step behaviour:**
  - **queries:** build `DiscoveryInput` → the plan → `metadata.plan` (JSON). An empty plan → `search` is `skipped`.
  - **search:** for each planned query not in `metadata.queries_done`, `search_repositories`. Then, per result:
    - prefilter;
    - `upsert_repository` + `replace_topics` (languages are left to analysis);
    - a new repository gets `lifecycle=discovered`, and an existing one keeps its state;
    - upsert `RepositoryCandidate` and `CandidateDiscovery` (rank = 1-based position).

    Per-query rejection counts go in `metadata.rejections`. A 422 → `metadata.queries_skipped`. A query is appended to `queries_done` after its writes commit.
  - **interactions:** contributor-linked repositories → prefilter (without stars) → candidate plus a `previously_interacted` discovery.
  - **analysis:** the developer's candidates whose repository needs work (`discovered`, `stale`, `failed` and due, or missing parts), ordered by (previously_interacted first, best search rank, full_name), capped at `DISCOVERY_MAX_ANALYSES_PER_RUN` (60; lower it, e.g. 10, for faster runs, and the backlog analyzes the rest). For each: check cancellation, `claim`, then `analyze`. Progress goes in `metadata.analyzed`. An unclaimable repository is skipped; the backlog task or a later run covers it.
  - **pool:** delete candidates with `last_seen_at < now − DISCOVERY_CANDIDATE_RETENTION_DAYS`, then enforce `DISCOVERY_MAX_POOL`. The kept candidates are the first `DISCOVERY_MAX_POOL` in analysis order (`previously_interacted` first, best search rank nulls last, `last_seen_at` newest, full_name); the rest are evicted. With `DISCOVERY_MAX_POOL` equal to `DISCOVERY_MAX_ANALYSES_PER_RUN`, the pool is exactly the analyzed top N. `CandidateDiscovery` rows for queries no longer planned are kept until their candidate expires, because they are still true history.
- **Clients:** the run builds one user client (`GitHubClient.for_user`) for search, and one user client with `cache_scope="public"` for repository endpoints.
- **Shared job runner:** the retry and finish loop currently inline in `sync_github_profile` moves to `services/jobs.run_tracked_job(task, job_id, runner)`. The sync and discovery tasks both use it. `repositories.generate_candidates(job_id)` (in `repositories/tasks.py`; there is no `discovery` Django app) is the task.
- **Starting jobs:**
  - `start_discovery(user)`: no-op without a `DeveloperProfile` or a `GitHubAccount`; it returns the active job instead of creating a second one (IntegrityError-safe, as `start_profile_analysis` does).
  - It is called by `run_tracked_job`'s success path for the sync and analysis job types, through `transaction.on_commit`, so a discovery failure cannot change the finished job.
- `active_jobs`/`_expire_stale` gain a `job_type` parameter, so a dead discovery run is expired too.
- **Parallel analysis:** the analysis step runs `DISCOVERY_ANALYSIS_CONCURRENCY` (4) threads. Each has its own `GitHubClient` (public scope) and database connection (closed when the thread ends) and takes repository IDs from a queue. The job's thread records each `(repo_id, outcome)` in `metadata.analyzed` as it arrives, so progress and resume work as before. Workers heartbeat and check cancellation between repositories. On an error the others stop taking new repositories and finish their current one; the finished ones are recorded, and the first error is re-raised for `decide_retry`. `1` runs sequentially in the job's thread, and the test settings use it because threads cannot see a test's transaction. The value stays low because GitHub asks for a user's requests to be mostly serial (secondary rate limits).
- **Alternative:** a Celery chord fanning out `sync_repository` per candidate. Rejected: chords need a result backend and are fragile with `acks_late` on Redis, and per-repository progress on one job is simpler to resume and report.

### D8. Staleness and background refresh (`services/repositories/staleness.py` + beat)
- `stale_parts(repo, now, ages) -> list[str]` is pure. `REPO_STALE_AFTER` (hours) defaults: `{"metadata": 12, "activity": 24, "community": 168, "dependencies": 168, "readme": 168}`. A part with no timestamp is stale.
- **Task `repositories.mark_stale_repositories`** (beat, hourly): pages through `recommendable|indexed` repositories that have at least one candidate, and sets `stale`, `stale_parts` and `previous_lifecycle`.
- **Task `repositories.process_repository_backlog`** (beat, every 15 min):
  - selects up to `REPO_REFRESH_BATCH` (50) pooled repositories: `stale`; `discovered` with `lifecycle_changed_at` older than `REPO_DISCOVERED_GRACE_MINUTES` (10); `failed` older than `REPO_FAILED_RETRY_HOURS` (24); or `fetching | refreshing` older than `SYNC_STALE_AFTER_SECONDS` (a dead worker's claim);
  - orders them by `lifecycle_changed_at`;
  - enqueues `sync_repository_readme` or `sync_repository` per repository (IDs only);
  - no-ops with a warning when `GITHUB_CLIENT_ID`/`SECRET` are empty.
  - A rate limit inside `sync_repository` → `self.retry(countdown=...)` from `decide_retry`, with the repository released.
- **Claim timestamps** use the wall clock, never a job's reference `now`: a discovery run analyzes with the time it started, and stamping claims with it would make every claim after `SYNC_STALE_AFTER_SECONDS` look abandoned to other workers.
- **Task `jobs.recover_stale_jobs`** (beat, every `JOB_RECOVERY_INTERVAL_SECONDS`, 5 min): RUNNING jobs with `updated_at` older than `SYNC_STALE_AFTER_SECONDS` (10 min) are requeued to their task (`claim_job` reclaims them, and a duplicate delivery is refused because the reclaim refreshes `updated_at`). Jobs at `SYNC_MAX_ATTEMPTS` end as FAILED `worker_lost`. Without it, a job killed with its worker (acks_late) waited for Redis's one-hour `visibility_timeout` and showed RUNNING meanwhile. Jobs heartbeat in `_check_cancelled` (between repositories, queries and steps), and every unit of work is bounded by `GITHUB_HTTP_TIMEOUT` and `REDIS_SOCKET_TIMEOUT`, so ten minutes without a heartbeat means a dead worker.
- `CELERY_BEAT_SCHEDULE` is defined in `config/settings/base.py`.
- **Local beat:** `scripts/beat.mjs` runs `celery -A config beat --schedule <tmp file>` through `uv`, and `scripts/start.mjs` starts it next to the worker when `REDIS_URL` is set. (Embedded `worker -B` is not supported on Windows.)
- **Why app credentials for refresh:** repositories are shared, so borrowing an arbitrary pool member's token would spend one user's quota on others' behalf and break when that user disconnects. The OAuth app's client credentials have their own public-data limit, and need no user.

### D9. Configuration and system check
- **Settings** (env-overridable; JSON for dicts):
  - discovery: `DISCOVERY_MAX_QUERIES`, `DISCOVERY_QUERY_SHARES`, `DISCOVERY_RESULTS_PER_QUERY` (30), `DISCOVERY_MIN_STARS` (20), `DISCOVERY_MAX_PUSH_AGE_DAYS` (180), `DISCOVERY_MIN_SKILL_CONFIDENCE` (0.3), `DISCOVERY_MAX_ANALYSES_PER_RUN` (60), `DISCOVERY_MAX_POOL` (300), `DISCOVERY_CANDIDATE_RETENTION_DAYS` (30);
  - repositories: `REPO_README_MAX_BYTES` (204800), `REPO_SNAPSHOT_HISTORY` (10), `REPO_STALE_AFTER`, `REPO_REFRESH_BATCH`, `REPO_DISCOVERED_GRACE_MINUTES`, `REPO_FAILED_RETRY_HOURS`;
  - activity: `ACTIVITY_THRESHOLDS`.
- The `core/checks.py` check is extended to reject:
  - non-positive budgets or caps;
  - `DISCOVERY_RESULTS_PER_QUERY > 100`;
  - unknown share or stale-part keys;
  - moderate thresholds stricter than recent ones.
- Everything is documented in `.env.example`.

### D10. API (`repositories/api.py`, `/api/v1/discovery/…`)
- **`GET /discovery/status`** → `{job: SyncJob | null, last_completed_at, pool: {total, eligible, awaiting_analysis, ineligible, by_source: {source: n}}}`.
  - `awaiting_analysis` = candidates whose repository has `is_eligible IS NULL`.
  - Computed with one aggregate query plus one for `by_source`.
- **`GET /discovery/candidates`**: paginated.
  - Loading: `select_related("repository")`, `prefetch_related("discoveries", "repository__topics")`, and the latest snapshot label through a `Subquery` annotation, so the query count is constant.
  - django-filter: `source` (exists a discovery), `eligible` (bool), `activity` (label).
  - Ordering: eligibility state (eligible, awaiting analysis, ineligible), then the analysis order (previously_interacted first, best search rank nulls last, full_name), so analysed candidates are not scattered through the list. Search rank is GitHub's order within one query, not a ContribFinder score.
  - The item shape is as in the spec. `lifecycle` is exposed because it is useful for debugging and is not a score.
- Both endpoints are authenticated, per-user, and in the OpenAPI schema. `npm run api:sync` regenerates the types.

### D11. Frontend
- `useDiscoveryStatus()` (TanStack Query) polls every 3 s while `job.status` is active, and is invalidated when a sync completes, because a sync completion starts discovery.
- `DiscoveryCard` on the profile page (state machine):
  - no job → "We'll look for projects after your profile is ready";
  - active → "Finding projects that match your profile…";
  - completed → "{eligible} candidate projects found · updated {relative time}";
  - failed → a message from `messages.ts` (codes `github_auth_invalid`, `github_rate_limited`, `github_unavailable`, default).
- There is no list, score or percentage. Recommendations replace this card's call to action in Phase 5.

## Risks / Trade-offs

- **[Search API limit of 30/min per user]** → ≤ 10 queries per run. A secondary limit goes through the existing `Retry-After` retry, and the run resumes per query.
- **[~10 requests per analyzed repository, on the user's 5,000/h budget]** → The cap is 60 analyses per run (~600 requests). Fresh shared repositories are skipped, and ETags are shared (`public` scope). The rest is picked up by the app-credential backlog.
- **[App client-credential rate limit is shared by all users]** → Batches of 50 every 15 minutes (≤ ~2,000 requests/h worst case). Rate limits are retried via `Retry-After`. The backlog only touches pooled repositories.
- **[Client-credential (Basic) auth for public data could be restricted by GitHub]** → It is isolated in `for_app()`. If it stops working, the backlog logs and no-ops, and discovery runs still analyze with user tokens. *Verified 2026-09-29:* `GET /rate_limit` with the app's client credentials returns `core` 5,000/h and `search` 30/min, and `GET /repos/encode/httpx` succeeds with `X-RateLimit-Limit: 5000`.
- **[Commit/contributor counts via `per_page=1` + `Link: last` depend on GitHub's pagination]** → Fixture tests pin the behaviour. A missing link falls back to the item count, and the contributor count is nullable.
- **[The PR sample is capped at 100]** → `prs_sample_capped` is stored. Thresholds (5 merged) sit far below the cap, so the label is unaffected.
- **[Search results favour popular repositories]** → Accepted for MVP. Ranking and label signals in Phase 5 matter more than search order, and `DISCOVERY_MIN_STARS` is configurable.
- **[A profile change while discovery runs uses the old skills]** → The next sync or analysis starts a new discovery. The one-active constraint prevents overlap.
- **[`Repository.lifecycle` on rows shared with owned repositories]** → The backlog and staleness only consider pooled repositories. The owned-repository sync never touches lifecycle fields.
- **[Moving helpers out of `sync.py`]** → A pure move with re-exports. The existing Phase 2/3 sync tests must stay green unchanged.

## Migration Plan

Additive migrations:
- the new `Repository` columns (defaults and nulls; `lifecycle=discovered` for existing rows);
- `RepositoryReadme`, `RepositorySnapshot`, `RepositoryCandidate`, `CandidateDiscovery`;
- the new `SyncJob.JobType` choice.

Existing users get a pool after their next sync or re-analysis. An operator can also run `reanalyze_profiles`, which chains discovery through D7. Rollback: revert the code and migrations; only the new tables and columns are dropped.

## Open Questions

- The default query shares and `DISCOVERY_MIN_STARS` will need tuning once real pools can be inspected. They are configuration, and Phase 8b evaluation decides their final values.
