# Changelog

All notable changes to ContribFinder are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows
[Semantic Versioning](https://semver.org/). Before the MVP, each completed roadmap phase bumps
the minor version (`0.x.0`).

## [Unreleased]

## [0.7.0] - 2026-10-13

Phase 7: Issues (OpenSpec change `phase-7-issues`; FR-ISSUE-001..005, MVP+). Issue analysis and
matching are deterministic and rule-based: no LLM or embedding calls.

### Added

- New `issues` app. `Issue` stores the open issues of every pooled repository once, shared by all
  developers: GitHub fields (title, plain-text body capped at `ISSUE_BODY_MAX_CHARS`, raw labels,
  locked, assignee, comments, times) plus ContribFinder analysis with its evidence.
  `RecommendedIssue` holds each recommendation's relevant issues (rank, internal score, reasons)
  and is rebuilt with it.
- Issue ingestion (FR-ISSUE-001): `GitHubClient.list_open_issues` (most recently updated first,
  `ISSUES_MAX_PAGES` pages of 100, pull requests dropped, truncation recorded, 410 = issues
  disabled). Issues are a repository analysis part with their own staleness
  (`REPO_STALE_AFTER["issues"]`, 6 h); the backlog queues the new task
  `repositories.sync_repository_issues` when only issues are stale. Each fetch replaces the
  stored set, so closed issues disappear; a failed fetch keeps them and is recorded.
- Label normalization (FR-ISSUE-002): an alias table with scope-prefix stripping (`Type: Bug`,
  `kind/docs`, `good-first-issue`) maps raw labels to 13 canonical categories
  (`ISSUE_TAXONOMY_VERSION`). Raw labels are kept as sent.
- Contribution type (FR-ISSUE-003): code, documentation, testing, bug fix, feature, DevOps,
  design or unknown, from label priority first and title keywords second, with the deciding
  label or keyword recorded.
- Difficulty (FR-ISSUE-004): beginner, intermediate, advanced or unknown from signal votes
  (difficulty labels, description length, technologies mentioned, documentation work, discussion
  size; thresholds in `ISSUE_DIFFICULTY`). A level needs two agreeing votes and no contradiction,
  so a label alone never decides. Every vote is stored as evidence.
- Issue technologies: the skill catalog detects technologies in an issue's title, labels and body
  (ambiguous words only in labels; HTML and CSS left out).
- Issue matching (FR-ISSUE-005): eligible issues (open, unlocked, unassigned, updated within
  `ISSUE_MAX_AGE_DAYS`) are scored per developer from technology match, difficulty fit with the
  internal experience level and approachability labels. Up to 5 relevant issues per
  recommendation, each with reasons built only from those parts.
- Two repository signals, `issue_fit` and `difficulty_fit`, with reason types
  `issue_availability` and `difficulty`. Issues alone never make a project a recommendation.
- API: `relevant_issue_count` on recommendation list items; `difficulty` and `contribution_type`
  filters; relevant issues on the recommendation detail; `GET /api/v1/issues/{id}` with GitHub
  data and ContribFinder analysis as separate objects (404 unless relevant to one of the user's
  recommendations). `opened_issue` feedback now requires `issue_id` and stores the issue and a
  number snapshot.
- Frontend: "N relevant issues" on cards, the two new filters, a "Relevant issues" section on
  the repository detail page, and the issue page `/app/issues/:id` ("From GitHub" vs
  "ContribFinder analysis", description as plain text, "Not enough evidence" for unknown values,
  GitHub link recording `opened_issue`).
- Settings `ISSUES_MAX_PAGES`, `ISSUE_BODY_MAX_CHARS`, `ISSUE_MAX_AGE_DAYS`, `ISSUE_DIFFICULTY`
  with system check `core.E040`.

### Changed

- **Ranking change:** new scoring configuration `v2-deterministic` (skill 0.35, language 0.15,
  interest 0.15, framework 0.10, activity 0.10, openness 0.05, issue fit 0.05, difficulty fit
  0.05, plus issue matching parameters) is activated by migration. The freshness sweep
  regenerates every user's recommendations under it. Projects without relevant issues score a
  little lower than under v1 (for example Strong can become Good). `v1-deterministic` stays
  stored and can be re-activated from the admin; it scores the issue signals as 0.
- Issue difficulty and the profile's preferred difficulty share one choice set (OpenAPI
  `DifficultyEnum`).

### Known limitations

- One page of the most recently updated issues per repository: older good first issues in large
  repositories can be missed (truncation is recorded).
- Rule-based difficulty is often `unknown` (shown as "Not enough evidence").
- Every issue refresh (6 h) makes the pool's recommendations due for regeneration.
- Docker Compose verification remains future scope.

## [0.6.0] - 2026-10-01

Phase 8a: Feedback and data controls (OpenSpec change `phase-8a-feedback-data-controls`;
FR-FEEDBACK-001..004, FR-DATA-002, FR-DATA-003). Completes the MVP definition of done. Feedback
is recorded for analytics and evaluation only: it does not change ranking.

### Added

- New `feedback` app: `RecommendationFeedback` (viewed, saved, unsaved, dismissed, undismissed,
  opened repository, opened issue), stored independently of the recommendation with snapshots of
  the repository name, match label, rank and scoring config version. It survives regenerations
  and repository deletion (`SET_NULL`). Views are de-duplicated per recommendation within
  `FEEDBACK_VIEW_DEDUP_MINUTES` (30, system check `core.E020`).
- Save: `SavedRepository` (unique per user and repository). Saved projects survive regenerations
  and stay listed when they are no longer recommended. Recommendation list and detail carry a
  `saved` flag.
- Dismiss: `DismissedRepository`. Dismissing deletes the recommendation and any save, and the
  repository is excluded from every later ranking run (`load_candidates`, and re-checked inside
  the generation transaction so a dismissal during a run is honored). Restoring it starts a new
  generation.
- Feedback API: `POST /recommendations/{id}/feedback`, `POST|DELETE /recommendations/{id}/save`,
  `POST /recommendations/{id}/dismiss`, `GET /saved`, `DELETE /saved/{repository_id}`,
  `GET /dismissed`, `DELETE /dismissed/{repository_id}`.
- Data deletion (`services/data_deletion.py`), one routine for every path: cancels the user's
  jobs, deletes the GitHub profile and README, repository links, developer profile (skills,
  interests, evidence, candidate pool, recommendations), saves, dismissals, feedback and job
  history, removes shared repositories no one references any more, and purges the user's cached
  GitHub responses.
- `DELETE /api/v1/profile/github-data`: deletes GitHub-derived data and keeps the account and the
  GitHub connection, so the user can sync again.
- `DELETE /api/v1/auth/account`: revokes the GitHub grant (a failure is recorded, deletion still
  proceeds), deletes the data and the account, and ends the session.
- Audit actions `github_data_deleted` and `account_deleted` (with deletion counts). Audit entries
  survive account deletion without the user reference.
- Dashboard: Save/Saved and Dismiss (with Undo) on cards and the detail page; `viewed` and
  `opened_repository` events (never blocking); `/app/saved` page with saved projects ("No longer
  recommended" note) and hidden projects with Restore; a pipeline stage line next to Refresh
  (syncing, analyzing, finding projects, preparing recommendations); a "Your data" section with
  confirmed delete actions.
- Public `/privacy` page: what is stored, why, how long, and how to delete it. Linked from the
  landing page and "Your data".

### Changed

- **Behavior change:** disconnecting GitHub now also deletes all GitHub-derived data (SRS-2 §66),
  keeping only the account and its audit trail. Reconnecting starts from scratch. The disconnect
  dialog says so, and its audit entry records the deletion counts.

### Fixed

- Ctrl+C now stops `npm start` in an interactive Windows console (Anaconda Prompt, cmd). The
  `wsl.exe` processes that start and keep Redis alive switched the shared console's input to raw
  mode; `scripts/redis.mjs` now gives each one its own hidden console.
- The dashboard kept showing "No suitable projects yet" after a refresh when the recommendation
  generation finished between two status polls; the list now reloads whenever a new finished
  generation appears.
- The "Hidden … Undo" notice did not appear after dismissing a project: the card is removed
  before the request returns, which dropped the success callback.

### Known limitations

- Feedback does not influence ranking yet (post-MVP); evaluation arrives with Phase 8b.
- `opened_issue` is accepted but has no source until issues arrive (Phase 7).
- Docker Compose verification remains future scope.

## [0.5.0] - 2026-09-29

Phase 5: Recommendation engine, deterministic (OpenSpec change `phase-5-recommendation-engine`;
FR-REC-001..006). No LLM or embedding calls; scoring reads stored data only.

### Added

- Repository technologies (`services/matching/technologies.py`): the skill catalog maps a
  repository's languages (byte share), topics and dependency manifests to skills, with the source
  of each detection.
- Six relevance signals (`services/matching/signals.py`), each 0..1 with the evidence it used:
  skill match (weighted stack coverage), language match (code share × confidence), framework match
  and interest match (noisy-OR), activity signal (activity label) and contribution openness
  (contributing guide, issue templates, good-first-issue and help-wanted labels).
- Versioned scoring configuration (`ScoringConfig`, one active): weights, match-label bands and
  signal parameters, validated on save. Seeded `v1-deterministic` (skill 0.40, language 0.20,
  interest 0.15, framework 0.10, activity 0.10, openness 0.05; strong ≥ 0.55, good ≥ 0.35),
  marked experimental. Admin "Activate" action; configs in use cannot be edited or deleted.
- Ranking (`services/ranking/`): weighted score, Strong/Good/Partial labels, tie-break by search
  rank then name, top N (`RECOMMENDATIONS_TOP_N`, 50) above `RECOMMENDATION_MIN_SCORE` (0.10).
  A candidate needs at least one skill, language, framework or interest match: activity and
  openness alone never make a recommendation.
- `Recommendation` (non-null FK to the config that produced it, per-signal scores, technologies,
  activity, size) and `RecommendationReason` (type, text, contribution, JSON detail), built only
  from non-zero signals. Texts use words, never percentages.
- Generation job `recommendation_generation` (task `recommendations.generate_recommendations`):
  starts after every completed discovery, writes in one transaction, upserts per repository so ids
  stay stable, and keeps the previous results on failure or cancellation.
- Freshness: beat task `recommendations.refresh_recommendations` (every 30 minutes) regenerates
  when the profile, a pooled repository or the active config changed since the last generation.
- API: `GET /api/v1/recommendations` (rank order; filters `language`, `framework`, `activity`,
  `size`, `match`; 400 on unknown values), `GET /api/v1/recommendations/{id}` (language breakdown,
  README excerpt, contribution facts, activity signals) and `GET /api/v1/recommendations/status`.
  No score or rank is exposed.
- Dashboard "Recommended projects": cards with match label, top reasons, technologies (matched
  highlighted), activity and a GitHub link; URL-backed filters shown when there is more than one
  page (20) or a filter is active; pagination; generating and empty states.
- Repository detail page (`/app/recommendations/:id`) separating "From GitHub" (overview, topics,
  languages, activity, contribution guidelines, README) from "ContribFinder analysis" (why it
  matches, technologies, activity label, size).
- Settings `RECOMMENDATIONS_TOP_N`, `RECOMMENDATION_MIN_SCORE`, `REPO_SIZE_THRESHOLDS`,
  `RECOMMENDATION_REFRESH_INTERVAL_SECONDS`, `RECOMMENDATION_README_EXCERPT_CHARS`, with a system
  check (`core.E030`–`E032`).

### Changed

- Disconnecting GitHub also cancels an active recommendation generation.
- `jobs.recover_stale_jobs` also requeues recommendation generation jobs.

### Known limitations

- Save, dismiss and feedback on recommendations arrive with Phase 8a.
- Difficulty fit, issue fit and the difficulty and contribution-type filters arrive with issues
  (Phase 7).
- With the local pool capped at 10 (`.env`), at most 10 recommendations are generated.
- Ctrl+C still does not stop `npm start` in an interactive Windows console (Anaconda Prompt): use
  `npm run stop`. Carried to the next phase.
- Docker Compose verification moved to future scope.

## [0.4.0] - 2026-09-29

Phase 4: Repository discovery (OpenSpec change `phase-4-repository-discovery`; FR-REPO-001..004).
Builds a per-developer candidate pool. Nothing is ranked or recommended yet (Phase 5).

### Added

- Query generation (`services/discovery/queries.py`): the developer's top skills, interests,
  languages and repository topics become GitHub search queries in four strategies (language,
  skill, interest, topic) within a per-run budget (`DISCOVERY_MAX_QUERIES`, default 10). Every
  query carries the hard filters: not archived, not a fork, public, pushed recently, minimum
  stars, not the user's own repositories.
- Repository discovery job (`repository_discovery`, task `repositories.generate_candidates`) with
  resumable steps queries → search → interactions → analysis → pool. It starts automatically
  after a completed profile sync or profile analysis. Repositories the user contributed to join
  as `previously_interacted`.
- Candidate provenance: `RepositoryCandidate` (one per developer and repository) and
  `CandidateDiscovery` (source, query, search rank, first/last seen).
- Filtering as its own stage: a pre-filter on search results and an eligibility check on analyzed
  data, each rejection recorded with a reason code (`archived`, `fork`, `inactive`, `no_license`,
  `few_stars`, `own_repository`, `repository_unavailable`).
- Shared repository analysis (`services/repositories/`): metadata, languages, topics, README (stored
  raw, truncated at a cap), community files (CONTRIBUTING, code of conduct, issue/PR templates),
  `good first issue` / `help wanted` labels and dependency manifests, each with its own refresh
  timestamp.
- Repository lifecycle: `discovered → fetching → analyzed → indexed → recommendable`,
  `stale → refreshing`, and `failed` with an error code. Eligibility is stored separately.
- Activity signals (`services/matching/activity.py`): days since push, commits and pull requests
  in 90 days, contributors, latest release, open issues → `RepositorySnapshot` with a label
  `recently_active | moderately_active | low_activity`. Thresholds are configuration.
- Celery beat: `mark_stale_repositories` (hourly), `process_repository_backlog` (every 15 minutes,
  app client credentials, public data only), `jobs.recover_stale_jobs` (every 5 minutes).
- `GET /api/v1/discovery/status` and `GET /api/v1/discovery/candidates` (paginated, filterable by
  source, eligibility and activity; stored data only; no score or rank).
- Profile page "Project discovery" card (state, candidate count, last updated).
- Dead-worker recovery: jobs record a heartbeat between units of work; a RUNNING job without one
  for `SYNC_STALE_AFTER_SECONDS` (default 10 minutes) is requeued, or ends as FAILED
  `worker_lost` once it has used all attempts.
- Parallel repository analysis within a discovery run (`DISCOVERY_ANALYSIS_CONCURRENCY`, default
  4 threads, each with its own GitHub client and database connection).
- Local tooling: `scripts/beat.mjs` (Celery beat), `scripts/frontend.mjs` (Vite without `npm.cmd`),
  `scripts/child.mjs` (runners kill their whole process tree and stop when `npm start` is gone),
  and `npm run stop` (kills a leftover local stack of this repository).

### Changed

- The candidate list is ordered eligible → awaiting analysis → ineligible, then previously
  interacted, best search rank and name (the order the job analyzes them), instead of by
  last-found time.
- The pool cap keeps the best candidates in analysis order and evicts the rest (previously: the
  least recently found). With `DISCOVERY_MAX_POOL` equal to `DISCOVERY_MAX_ANALYSES_PER_RUN`, the
  pool is exactly the analyzed top N.
- `SYNC_STALE_AFTER_SECONDS` default lowered from 30 to 10 minutes.
- On Windows the local Celery worker runs `--pool=threads --concurrency=4` (was `--pool=solo`),
  so discovery, syncs and backlog refreshes run side by side.
- Repository storage helpers moved from `services/github/sync.py` to `services/github/storage.py`;
  the job retry/finish loop moved to `services/jobs.run_tracked_job`.

### Fixed

- A job killed together with its worker stayed RUNNING for up to an hour (Redis visibility
  timeout), and the discovery card kept spinning.
- Redis calls had no socket timeout, so a stalled connection (a sleeping WSL distro) could hang a
  worker; `REDIS_SOCKET_TIMEOUT` (default 5 s) now applies to the cache and the broker connect.
- Repository claims were stamped with the discovery job's start time, so after 10+ minutes other
  workers saw them as abandoned. Claims now use the wall clock, and the backlog also takes over
  claims left by a dead worker.
- Flaky frontend tests: under parallel load a first render could outlast Testing Library's 1 s
  default for `findBy*`/`waitFor`. The shared setup now allows 5 s (`asyncUtilTimeout`), and
  Vitest's per-test timeout is 15 s.
- The changelog was missing its `0.2.0` heading.

### Known limitations

- Ctrl+C does not stop `npm start` in an interactive Windows console (Anaconda Prompt, cmd); use
  `npm run stop` from a second prompt. Tracked in CLAUDE.md §6 Known issues and carried to Phase 5.
- Docker Compose is still unverified (no Docker on the development machine); carried to Phase 5.
- `npm run api:sync` needs `uv` on PATH (`api:export` calls it directly).

## [0.3.0] - 2026-09-29

Phase 3: Developer profile, deterministic (OpenSpec change `phase-3-developer-profile`;
FR-PROFILE-001..005). No LLM or embedding calls.

### Added

- Skill and interest catalog (`services/profiling/taxonomy.py`, `TAXONOMY_VERSION`): 170 skills
  in 7 categories (language, framework, library, database, cloud, devops, tool) with aliases,
  GitHub language names, topics, badge/icon tokens and per-ecosystem dependency names; 16
  interests with synonyms and topics. Ambiguous words ("Go", "Rust", "Spring") only count in
  README tech sections, badges and skill icons.
- Two new sync steps:
  - `dependencies`: root manifests (requirements.txt, pyproject.toml, package.json, go.mod,
    Cargo.toml, pom.xml, build.gradle/.kts) of up to 30 recently pushed non-fork repositories,
    stored as `RepositoryDependency` names (raw files are not stored);
  - `contributions`: merged pull requests (search API) and recent public pushes to other
    people's repositories. Up to 20 of those repositories are stored with languages and topics
    and linked to the user as `contributor`. A 422 from search skips the step.
- Evidence collectors for README (sections, shields.io badges, skillicons.dev, devicon, alt
  text), repository languages, topics, dependencies, pull requests, pushes and repeated
  contributions. Every skill and interest has relational evidence rows (source, supporting
  repository, detail, observed date).
- Configurable confidence: `EVIDENCE_WEIGHTS` (SRS-1 §15 defaults) with diminishing returns per
  source and a 0.99 cap, so one README mention stays at 0.20. A system check refuses to start
  with invalid weights. Each profile records the weights and catalog version it used.
- `DeveloperProfile`: summary from fixed templates (computed signals only), language breakdown,
  default preferences, and an internal experience level (never shown or returned by the API).
- Analysis runs as the final `analysis` sync step and as a standalone `profile_analysis` job.
  `manage.py reanalyze_profiles [--user ID]` rebuilds profiles from stored data without GitHub
  calls. A failure (`analysis_failed`, not retried) keeps the previous profile.
- API: `GET /api/v1/profile` (404 `not_analyzed`), `GET /api/v1/profile/skills` (evidence,
  `?category=`), `GET /api/v1/profile/interests`.
- Frontend: `/app` is now the profile page: summary, skills grouped by category with bars labeled
  by evidence ("8 repositories · dependencies · README", never a percentage), expandable evidence
  with repository links, interests, and a Recharts languages chart (loaded lazily). Onboarding
  shows all eight steps.
- `npm run manage -- <command>` runs Django management commands without uv on PATH.
- Tests: 306 backend and 31 frontend. Verified end to end with a real account, including
  `reanalyze_profiles` on a Celery worker.

### Changed

- `GET /api/v1/profile/repositories` lists only repositories the user owns.
- Sync jobs report steps missing from older jobs as `pending`.
- `claim_job` / `finish_job` moved to `services/jobs.py` for reuse by all job types.

## [0.2.0] - 2026-09-28

Phase 2: GitHub data ingestion (OpenSpec change `phase-2-github-ingestion`; FR-GH-001..007, FR-DATA-001).

### Added

- Background GitHub sync fetches the user's profile, profile README (stored raw), public owned
  repositories (up to 100, most recently pushed), their languages (bytes) and topics into
  PostgreSQL. Later phases read this stored data instead of calling GitHub.
- GitHub client (`services/github/client.py`):
  - follows pagination (with a page cap) and uses ETag conditional requests (a 304 reuses the
    cached body);
  - handles primary and secondary rate limits (`Retry-After` / reset time) and maps errors to
    typed exceptions;
  - only follows pagination links on the API host.
- Tracked, resumable jobs (`SyncJob`): PENDING → RUNNING → COMPLETED / FAILED / RETRYING /
  CANCELLED, with per-step progress, attempt count and a safe error code.
  - A database constraint allows only one active job per user.
  - Retries never repeat completed steps.
  - Rate-limit waits and exponential backoff are capped.
  - A token rejected by GitHub (401) fails the job immediately, without retrying.
- API:
  - `POST /api/v1/profile/sync` returns 202, or 409 `github_not_connected`, or 429 `sync_cooldown`
    with `Retry-After`;
  - `GET /api/v1/sync/status`;
  - `GET /api/v1/profile/github`;
  - `GET /api/v1/profile/repositories` (paginated, `page_size` up to 100).
- The first sign-in starts a sync automatically. Disconnecting GitHub cancels any sync in progress.
- Frontend:
  - an onboarding screen with live per-step progress and messages for each failure;
  - a dashboard with profile, language breakdown, repositories, last-synced time and Refresh
    (with a cooldown message).
- Local development uses real background processing: `npm start` now also starts the WSL Redis
  service (Windows) and a Celery worker (`--pool=solo`). `REDIS_URL` defaults to
  `redis://localhost:6379/1`.
- `npm run check:version` also checks the three lockfiles.
- Tests: 142 backend and 22 frontend. Verified end to end with real GitHub: the first sync
  completed on the first attempt (~9s), and the Refresh cooldown works.

### Changed

- Custom API exceptions keep their own error code; for example `not_synced` is no longer reported
  as `not_found`.
- Logout moved into a shared signed-in layout. The disconnect text now says that synced data is
  kept until data deletion ships.

### Fixed

- Test isolation: respx routes registered outside an active mock leaked into later tests. Tests now
  use the `respx_mock` fixture, and an autouse guard resets the global router.
- `npm start` / `npm run setup` failed with "uv not found" when uv was installed via
  `pip install --user` (not on PATH) and `python` was the Microsoft Store stub. The runner now
  also checks standard install folders (`%APPDATA%\Python\Python3xx\Scripts`, `~/.local/bin`,
  `~/.cargo/bin`), accepts a `UV_BIN` override, and lists everything it tried.

### Known limitations

- Synced GitHub data is kept after disconnect until data deletion ships (FR-DATA-003, Phase 8a).
- No automatic periodic refresh yet; syncs run on first sign-in or on Refresh.
- The Docker Compose stack is still unverified (no Docker on the development machine).

## [0.1.0] - 2026-09-28

Phase 1: Foundation (OpenSpec change `phase-1-foundation`; FR-AUTH-001..003).

### Added

- Monorepo: `apps/backend` (Django 5.2, DRF, Celery) and `apps/frontend` (React 19, TypeScript,
  Vite, Tailwind v4, shadcn/ui, TanStack Query, React Router).
- GitHub sign-in through an OAuth App with no scopes (public data only). The flow uses a single-use
  `state`, and the user is matched by GitHub ID, so signing in again after disconnecting reuses the
  same user.
- GitHub access tokens are encrypted at rest (MultiFernet with key rotation). They are never
  returned to the client, and a log filter masks them as a backstop.
- Session auth with HTTP-only cookies and CSRF protection. New endpoints:
  `GET /api/v1/auth/github`, `GET /api/v1/auth/github/callback`, `GET /api/v1/auth/csrf/`,
  `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/github/disconnect`.
- Disconnect revokes the grant on GitHub and deletes the stored credential, even when the
  revocation call fails.
- Audit log for sign-in, failed sign-in, logout and disconnect. Metadata keys are allowlisted and
  client IPs are stored only as salted hashes.
- API platform:
  - every endpoint lives under `/api/v1/` and returns errors as `{"error": {code, message, details}}`;
  - unauthenticated requests get 401;
  - rate limiting returns 429 with `Retry-After`;
  - CORS allowlist and security headers;
  - `GET /api/v1/health/` checks the database and Redis;
  - OpenAPI schema at `GET /api/v1/schema/`.
- Frontend: landing page with messages for each sign-in error, a route guard, and a signed-in page
  with logout and a confirmed disconnect. API types are generated from the OpenAPI schema
  (`npm run api:sync`).
- Local development without Docker: `npm run setup` and `npm start` (Django on :8000, Vite on
  :5173) against a local PostgreSQL. Redis is optional; without it the cache is in-process, Celery
  tasks run inline, and health reports Redis as `not_configured`.
- Docker Compose stack: Postgres with pgvector, Redis, backend, Celery worker and beat, frontend.
- CI (GitHub Actions):
  - backend: ruff, strict mypy, migration check, pytest on Postgres;
  - frontend: eslint, prettier, tsc, vitest, build;
  - checks that the committed API schema matches the backend, and that the version is consistent
    across `VERSION` and the manifests.
- Tests: 60 backend and 12 frontend.

### Security

- Production settings refuse to start without `REDIS_URL` and force HTTPS, HSTS and Secure
  cookies.
- System check `core.E001` blocks startup when `TOKEN_ENCRYPTION_KEYS` is missing or invalid.

### Known limitations

- The Docker Compose stack and the Celery worker in Docker have not been verified yet (no Docker on
  the development machine). This is carried over to Phase 2.
- The API contract version (`/api/v1`, OpenAPI `1.0.0`) is versioned separately from the app
  version.

[Unreleased]: https://github.com/SanjayJoshi116/ContribFinder/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/SanjayJoshi116/ContribFinder/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/SanjayJoshi116/ContribFinder/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/SanjayJoshi116/ContribFinder/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/SanjayJoshi116/ContribFinder/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/SanjayJoshi116/ContribFinder/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/SanjayJoshi116/ContribFinder/releases/tag/v0.1.0
