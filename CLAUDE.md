# CLAUDE.md

Guidance for Claude Code when working in this repository.

## 1. What ContribFinder is

A **developer-to-contribution-opportunity matching system**, not a GitHub search engine.
It builds an evidence-backed developer profile from GitHub data, discovers candidate
open-source repositories, ranks them deterministically, and explains every match.

Core loop (SRS-2 §87):

```
UNDERSTAND DEVELOPER → FIND CANDIDATES → UNDERSTAND PROJECTS → MATCH
→ EXPLAIN MATCH → IDENTIFY CONTRIBUTION OPPORTUNITIES → LEARN FROM INTERACTION
```

## 2. Sources of truth

- `Software Requirements Specification - 2.txt` (v2.0) is **authoritative** for what to build.
  Its §83 functional requirements (FR-*) are the implementation checklist.
- `Software Requirements Specification - 1.txt` (v1.0) supplies **concrete defaults**
  (model sketches, Celery task names, evidence weights, cache keys/TTLs, GitHubClient
  methods) wherever SRS-2 is silent. Where they conflict, SRS-2 wins.
- Accepted behaviour lives in `openspec/specs/` (synced when a change is archived). Read the
  relevant spec before changing its capability.
- Each phase below is specified in detail as an OpenSpec change under `openspec/changes/`
  before implementation. This file is the index; OpenSpec holds the per-phase specs and tasks.

### Resolved conflicts between SRS-1 and SRS-2

| Topic | Decision |
|---|---|
| Score display | Never show "87% match". UI shows match labels (Strong / Good / Partial) plus evidence. Numeric score is internal ranking only. |
| Ranking weights | Stored in a versioned `ScoringConfig` row; every `Recommendation` references the config that produced it. SRS-1 numbers are starting points only. |
| Semantic matching | Not in MVP. MVP ranking is fully deterministic. |
| LLM / embeddings | **Future scope.** No AI provider is chosen. MVP must not call any LLM or embedding API. AI lives behind interfaces added in Phase 6+. |
| Issue recommendations | **MVP+** (Phase 7), per SRS-2 §82. |
| Explanations | First-class `RecommendationReason` rows generated only from computed signals — never free-text invented. |
| Candidate provenance | `RepositoryCandidate` records *why* a repo entered a developer's pool (FR-REPO-002). |
| Skill evidence | Relational evidence rows (source, supporting repo, last observed), not an opaque JSON blob. |
| Difficulty | `beginner / intermediate / advanced / unknown`. Return `unknown` when evidence is insufficient. |
| Repo layout | Monorepo: `apps/backend`, `apps/frontend` (see §4). |

## 3. Non-negotiable invariants

Architecture (SRS-2 §85):
1. Modular monolith. No microservices, Kubernetes, Elasticsearch, or separate vector DB.
2. PostgreSQL is the system of record (pgvector only once embeddings arrive).
3. All GitHub and long-running work runs in **Celery** (Redis broker). HTTP requests never
   wait on GitHub; dashboard reads come from PostgreSQL.
4. Candidate generation → filtering → feature calculation → scoring → ranking → explanation
   are **separate, independently testable stages**.
5. Deterministic scoring owns final ranking. AI (when added) only extracts/classifies.
6. Weights and evidence strengths are configuration, not constants in code.
7. Repository activity is shown as observable signals ("Recently active"), never "healthy/good".

Product principles (SRS-2 §6): evidence over keywords; explainability over black-box scores;
a score is relevance, not probability of success; the user can filter, save, dismiss,
refresh, disconnect, and delete.

GitHub tokens and secrets:
- Never returned to the frontend, never logged, never in URLs, never in client code.
- Encrypted at rest (MultiFernet via `services/crypto.py`, keys from `TOKEN_ENCRYPTION_KEYS`).
- Minimum scope: **no OAuth scopes** (public data only; configurable via `GITHUB_OAUTH_SCOPES`).
- Revoked and deleted on disconnect.

Resilience:
- A missing profile README, GitHub failure, or (later) AI failure must degrade gracefully,
  never take down recommendations.
- Failures are recorded as state (`SyncJob.status=FAILED`, repo lifecycle), never
  silently treated as empty data.

## 4. Stack and layout

Backend: Python 3.12+, Django, DRF, django-environ, django-filter, drf-spectacular (OpenAPI),
Celery + Redis, PostgreSQL, pytest / pytest-django / factory_boy, ruff, mypy.

Frontend: React 19+, TypeScript, Vite, TanStack Query (server state), Zustand (client-only
state), Tailwind + shadcn/ui + lucide-react, React Hook Form + Zod, Recharts,
Vitest + React Testing Library, Playwright. API types are **generated from OpenAPI**, not handwritten.

```
ContribFinder/
├─ apps/
│  ├─ backend/
│  │  ├─ manage.py
│  │  ├─ config/            settings/{base,development,test,production}.py, urls.py, celery.py,
│  │  │                     exceptions.py (error envelope)
│  │  ├─ core/              health, auth class, CSRF/400/403/404 JSON views, log redaction, checks,
│  │  │                     startup (production check gate), throttling (cache-outage fallback)
│  │  ├─ accounts/          User, AuditEvent, auth views, session, data deletion
│  │  ├─ github/            GitHubAccount, GitHubProfile, sync task (tasks.py), profile API
│  │  ├─ jobs/              SyncJob (generic tracked jobs), sync status API, recover_stale_jobs task
│  │  ├─ developers/        DeveloperProfile, Skill, DeveloperSkill, SkillEvidence, Interest,
│  │  │                     DeveloperInterest, InterestEvidence; profile API; analysis task;
│  │  │                     reanalyze_profiles command
│  │  ├─ repositories/      Repository (lifecycle, eligibility), RepositoryLanguage, RepositoryTopic,
│  │  │                     RepositoryDependency, UserRepository (owner | contributor),
│  │  │                     RepositoryReadme, RepositorySnapshot, RepositoryCandidate,
│  │  │                     CandidateDiscovery; discovery API; discovery/refresh/beat tasks
│  │  ├─ issues/            Issue (shared, analysis on the row), RecommendedIssue; issue
│  │  │                     detail API (Phase 7)
│  │  ├─ recommendations/   ScoringConfig, Recommendation, RecommendationReason; API; generation
│  │  │                     and freshness tasks; evaluate_ranking, export_benchmark_developer,
│  │  │                     benchmark_sheet, import_judgments, build_benchmark commands
│  │  ├─ feedback/          RecommendationFeedback, SavedRepository, DismissedRepository; feedback,
│  │  │                     saved and dismissed API (Phase 8a)
│  │  ├─ embeddings/        (Phase 6, future)
│  │  ├─ evaluation/        data only: benchmark-v1.json (seed benchmark), holdout-v1.json and
│  │  │                     holdout-v2.json (acceptance only, never for choosing; both used, so
│  │  │                     the next search adds holdout-v3), benchmark-v2.json (personas plus
│  │  │                     judged real developers; selection benchmark once it exists),
│  │  │                     baselines.json (format 4, keyed by dataset, top N each)
│  │  └─ services/          crypto.py (token encryption), audit.py, jobs.py (start/claim/finish
│  │     │                  jobs), errors.py (PermanentJobError, JobCancelled), job_guard.py
│  │     │                  (stale_before, job_write, save_progress, heartbeat), locks.py
│  │     │                  (lock_developer: one lock order for recommendations and feedback),
│  │     │                  feedback.py
│  │     │                  (record, save, dismiss, restore), data_deletion.py (GitHub data /
│  │     │                  account deletion)
│  │     ├─ github/         oauth.py, accounts.py; GitHubClient, GitHubSyncService (Phase 2),
│  │     │                  storage.py (shared repository upserts)
│  │     ├─ profiling/      taxonomy, manifests, readme/collectors, confidence, interests,
│  │     │                  experience, summary, analysis (Phase 3)
│  │     ├─ discovery/      queries, filters (prefilter/eligibility), DiscoveryService (Phase 4)
│  │     ├─ repositories/   analysis, lifecycle, staleness (shared repository data, Phase 4)
│  │     ├─ issues/         labels (normalization), classify (type, difficulty),
│  │     │                  technologies, analysis (Phase 7)
│  │     ├─ matching/       activity, technologies, features (loading), signals,
│  │     │                  issues (issue matching) (Phase 4–7)
│  │     ├─ ranking/        config (validation), pipeline (rank_pool, shared by generation and
│  │     │                  evaluation), score, explain, service (generation), freshness (Phase 5)
│  │     ├─ evaluation/     dataset (benchmark load/validate, selection_dataset), metrics, runner
│  │     │                  (evaluate, compare, persona/real subsets), baseline, export, sheet
│  │     │                  (blind judging sheets), build (merge datasets) (Phase 8b+)
│  │     └─ ai/             provider interfaces only (future)
│  └─ frontend/src/{app,components,features,hooks,lib,api,types,routes}
├─ scripts/                 npm runners: start, stop, setup, backend, frontend, worker, beat,
│                           redis (WSL), child (process-tree runner), env, wait-port, uv,
│                           manage, check-version
├─ package.json             root runner: npm run setup / npm start / stop / manage / check:version
├─ docker-compose.yml       backend, worker, beat, postgres, redis, frontend
├─ VERSION, CHANGELOG.md, features.txt, Bug_Backlog.md (verified findings, fix batches),
│  ideas.md (unplanned gap analysis; each idea needs an OpenSpec change first)
└─ .github/workflows/ci.yml
```

## 5. Conventions

- Business logic lives in `services/`. Views, serializers and Celery tasks are thin
  wrappers that call services.
- Only `services/github/` talks to GitHub. It handles pagination, ETag conditional requests,
  timeouts, retries with exponential backoff, `Retry-After`/secondary rate limits, and
  Redis caching (`github:user:{u}`, `github:repo:{o}:{r}`, `github:issues:{o}:{r}`).
  The rest of the app sees normalized dataclasses, never raw GitHub JSON.
- Celery tasks are idempotent, create/update a `SyncJob`, and retry through Celery with backoff.
- Every DRF endpoint lives under `/api/v1/`, is paginated where it returns lists, enforces
  per-user authorization, and appears in the OpenAPI schema.
- Auth: Django session cookies (HTTP-only, Secure in prod, SameSite=Lax) plus CSRF (`X-CSRFToken`),
  with the SPA same-origin. Unauthenticated → 401. Every error uses
  `{"error": {code, message, details?}}` (`config/exceptions.py`).
- Scoring components are normalized to `0.0–1.0`.
- Tests: every service stage has unit tests; the GitHub client is tested against recorded
  fixtures, never the live API. Mock HTTP with `@respx.mock`, or the `respx_mock` fixture plus
  `@pytest.mark.respx(...)` for options. Never use `@respx.mock(...)` with kwargs and then register
  routes on the global `respx.mock`: they leak into other tests.
- Retry and backoff policies are pure functions (`services/github/retry.py`); Celery tasks only
  translate decisions into `self.retry(countdown=...)`.
- API errors: raise an `APIException` subclass with its own `default_code`; the handler keeps
  custom codes (`not_synced`, `sync_cooldown`, ...). Use `core.authentication.current_user(request)`,
  never `assert isinstance(request.user, User)`.

## 6. Commands

Local, no Docker (primary on this machine):
- one-time: create the PostgreSQL role/db `contribfinder` (see README), then `npm run setup`.
  This creates `.env` with generated secrets, installs deps and migrates.
- `npm start` runs Django on :8000 and Vite on :5173 together. Open http://localhost:5173.
  Runners use `scripts/child.mjs`, which kills the whole process tree on Windows so
  Celery/Python children are not orphaned, and stops it when the `npm start` process disappears
  (`CF_STACK_PID`; terminals such as Git Bash end only the top process). A leftover
  `Terminate batch job (Y/N)?` comes from `npm.cmd`: answer Y. Ctrl+C stops the stack,
  also in an interactive Windows console (fixed in Phase 8a, see Known issues below);
  `npm run stop` from a second prompt works too. It kills this repo's stack only (matched by executable and repo path).
  The SPA proxies `/api`.
- Redis: on Windows, `npm start` starts the `redis-server` service in WSL Ubuntu and keeps the
  distro awake (`scripts/redis.mjs`), then a Celery worker with `--pool=threads --concurrency=4`
  (`scripts/worker.mjs`). `REDIS_URL=redis://localhost:6379/1`: db 1, because db 0 holds unrelated
  data. With `REDIS_URL` empty, tasks run inline (syncs block) and health reports
  `redis: not_configured`. Production refuses to start without `REDIS_URL`.
- `uv` need not be on PATH: `scripts/uv.mjs` tries `UV_BIN`, PATH, standard install dirs
  (e.g. `%APPDATA%\Python\Python3xx\Scripts\uv.exe` from `pip install --user uv`) and
  `python -m uv`. In some terminals `python` is the Microsoft Store stub.
- `npm run manage -- <command> [args]` runs a Django management command in `apps/backend` the
  same way (e.g. `npm run manage -- reanalyze_profiles` after changing `EVIDENCE_WEIGHTS` or the
  skill catalog; it queues jobs, so a worker must be running when `REDIS_URL` is set).
- `npm run manage -- evaluate_ranking --config <v1> --config <v2>` scores configurations on the
  benchmark (`apps/backend/evaluation/`); a ranking change is an improvement only if it wins there
  (README "Evaluating a ranking change"). After an intended ranking change, rerun with
  `--write-baseline` and commit `baselines.json`, or the baseline test fails. Without `--dataset`
  it rewrites `benchmark-v1`, recorded datasets and the selection benchmark, merging per config
  (format 4, top N per dataset); it refuses `--min-score`. A new config also
  must not regress on a fresh acceptance holdout (`holdout-v1`/`-v2` are used; add `holdout-v3`
  first; spec `recommendation-evaluation`). A config's own `min_score` wins over the setting;
  `--min-score` overrides it.
- Real judged developers (README "Judging real developers"): `export_benchmark_developer` →
  `benchmark_sheet` (blind CSV) → `import_judgments` → `build_benchmark`. `evaluate_ranking`
  defaults to the selection benchmark: `benchmark-v2` once it holds a `real` developer, else
  `benchmark-v1`. Exports and sheets go in the gitignored `judging/` (paths `../../judging/...`,
  since commands run in `apps/backend`); committing `benchmark-v2` is the judge's call.

Docker (kept, not used here): `docker compose up --build`. Compose overrides `DATABASE_URL` /
`REDIS_URL` with container hostnames; Postgres is on host port 5433.

Backend (`apps/backend`, uses `uv`):
- `uv sync`: install deps
- `uv run pytest`: tests. Uses `config.settings.test` against local PostgreSQL (creates `test_contribfinder`)
- `uv run ruff check . && uv run ruff format --check .`: lint and format
- `uv run mypy .`: strict type check
- `uv run python manage.py makemigrations --settings config.settings.test`: new migrations

Frontend (`apps/frontend`, npm):
- `npm run dev`, `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run build`
- `npm run api:sync`: re-export the OpenAPI schema from Django and regenerate
  `src/api/schema.d.ts`. Run it after any API change and commit both files; CI fails on drift.

### Known issues

- **Fixed (Phase 8a): Ctrl+C did not stop `npm start` in an interactive Windows console.**
  Cause: `wsl.exe` (started by `scripts/redis.mjs`) switches its console's input to raw VT mode
  (`ENABLE_PROCESSED_INPUT` off, mode 0x1F7 → 0x3D8), so on the shared console Ctrl+C became a
  keystroke. Only happens when the runner's stdin is a pipe (under `concurrently`), which is why
  running a runner alone never reproduced it. Fix: every `wsl.exe` is spawned `detached` +
  `windowsHide`, so it gets its own hidden console. Any new runner that starts a console program
  (wsl.exe, ssh, ...) must do the same.
  - Testing note: processes started from Claude Code's shell inherit "ignore Ctrl+C", and
    `start /b` also starts children with Ctrl+C ignored. Launch test consoles through WMI
    (`Invoke-CimMethod Win32_Process Create`, `cmd.exe /K ...`), read the input mode with
    `AttachConsole` + `GetConsoleMode(CONIN$)` and send `GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)`.
    `GenerateConsoleCtrlEvent` bypasses the input mode and `WriteConsoleInput` does not raise a
    signal, so the input mode is the thing to check; confirm with a real key press.

## 7. Implementation roadmap (function by function)

Build in phase order. Each FR is one unit of work. A phase is done only when every FR in it
meets its **Done when** and its tests pass. Create one OpenSpec change per phase before
starting it.

### Phase 1 — Foundation  → *User can sign in with GitHub*  ✅ shipped in v0.1.0

Archived: `openspec/changes/archive/2026-09-28-phase-1-foundation/`. Specs: `api-platform`,
`github-authentication`.

Scaffolding: monorepo, docker-compose (backend, worker, beat, postgres, redis, frontend),
split settings via django-environ, Celery app, DRF plus drf-spectacular, Vite React TS app,
CI (ruff, mypy, pytest, eslint, prettier, tsc, vitest, build).

**FR-AUTH-001: GitHub authentication**
- Where: `accounts/`, `github/models.py`
- Build: `GET /api/v1/auth/github` (redirect with a `state` param), `GET /api/v1/auth/github/callback`
  (verify state, exchange code, upsert `User` and `GitHubAccount(github_id, username, avatar_url,
  encrypted access_token)`), frontend "Continue with GitHub" landing page.
- Done when: login creates a session; the token is stored encrypted and absent from every response and log.

**FR-AUTH-002: Authenticated session**
- Build: `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`, session expiry, CSRF endpoint.
  Frontend auth guard using TanStack Query on `/auth/me`.
- Done when: protected routes redirect when logged out; logout invalidates the session.

**FR-AUTH-003: Disconnect GitHub** (the endpoint lands here; data deletion in FR-DATA-003)
- Build: `POST /api/v1/auth/github/disconnect` → revoke the token through the GitHub API, then delete `GitHubAccount`.
- Done when: after disconnect the token no longer works and no copy of it remains.

### Phase 2 — GitHub data ingestion  → *User's GitHub data is in ContribFinder*  ✅ shipped in v0.2.0

Archived: `openspec/changes/archive/2026-09-28-phase-2-github-ingestion/`. Specs: `github-data-sync`, `sync-jobs`. The local real-worker
carry-over from Phase 1 is closed; Docker verification moves to Phase 3.

**Carry-over from phase-1-foundation:** the local Celery worker against real Redis (WSL) is
verified. `docker compose up` verification is still open (no Docker on the dev machine).

**SyncJob model**: `job_type, status (PENDING|RUNNING|COMPLETED|FAILED|RETRYING|CANCELLED),
user, started_at, completed_at, attempts, error, metadata`.

**FR-GH-001: Profile information**
- Build: `GitHubClient.get_authenticated_user()`; task `sync_github_profile`; store username,
  name, bio, company, location, blog, followers, following, public_repos, created_at.

**FR-GH-002: Public repositories**
- Build: `GitHubClient.get_repositories(username)`; task `sync_user_repositories`; persist the user's
  own repositories (owned, non-fork flag kept) with the metadata from SRS-2 §10.

**FR-GH-003: Repository languages**
- Build: `GitHubClient.get_languages(owner, repo)` → `RepositoryLanguage(repo, language, bytes)`.

**FR-GH-004: Repository topics**
- Build: topics from the repo payload → `RepositoryTopic`.

**FR-GH-005: Profile README**
- Build: `GitHubClient.get_readme(owner, repo)` (raw); look up `{username}/{username}`.
  Store the raw README separately from anything derived from it.
- Done when: users without a profile README still complete sync (`has_profile_readme=False`).

**FR-GH-006: Pagination**
- Build: a generic `_paginate()` in GitHubClient that follows `Link` headers, with a per-call page cap.

**FR-GH-007: Rate limits and transient failures**
- Build: timeouts, exponential backoff, `Retry-After` / `X-RateLimit-Reset` handling that
  schedules a Celery retry (never a hot loop), ETag conditional requests, Redis cache,
  rate-limit state in Redis.
- Done when: fixture tests cover 403/429 secondary limits, 5xx retry, and 304 not-modified.

**FR-DATA-001: Sync status**
- Build: `POST /api/v1/profile/sync` (enqueue, return job id), `GET /api/v1/sync/status`;
  onboarding screen polls the status and shows per-step ticks (Profile, README, Repos, Languages, Topics).
- Done when: the browser never blocks on a sync request; last-synced time is shown.

### Phase 3 — Developer profile (deterministic)  → *User sees a structured technical profile*  ✅ shipped in v0.3.0

Archived: `openspec/changes/archive/2026-09-29-phase-3-developer-profile/`. Specs:
`skill-detection`, `interest-detection`, `developer-profile` (plus deltas to `github-data-sync`
and `sync-jobs`). Docker verification is carried over to Phase 4.

Deviations from the sketch below, as built:
- `DeveloperProfile` has **no** `profile_readme_raw`: the raw README stays on `GitHubProfile`
  (raw data in one place). The profile also stores `languages`, `experience_signals` and
  `analysis_config` (weights, thresholds, `TAXONOMY_VERSION`).
- Analysis is the final `analysis` step of the GitHub sync (after new `dependencies` and
  `contributions` steps) and a standalone `profile_analysis` job (task
  `developers.extract_developer_skills`). Failures use `analysis_failed` and are not retried.
- Contribution evidence comes from merged PRs (search API) and recent public pushes (events
  API); contributed repos are stored and linked as `UserRepository(relation=contributor)`.
- Manifests also include `pom.xml` and `build.gradle(.kts)` (SRS-2 §13 lists Java build files).
- The summary names languages by skill confidence, not bytes, and ignores README-only skills.

**FR-PROFILE-001: Structured profile**
- Build: `DeveloperProfile(user, summary, experience_level, preferred_project_size,
  preferred_issue_difficulty, profile_readme_raw, analyzed_at)`; `GET /api/v1/profile`.

**FR-PROFILE-002: Identify skills**
- Build: `services/profiling/taxonomy.py`, a canonical skill catalog with aliases and categories
  (language, framework, database, cloud, devops, tool) and dependency-name mappings.
  Evidence collectors:
  - `readme_skills(readme)`: section and keyword extraction against the taxonomy
  - `language_skills(repo_languages)`
  - `topic_skills(repo_topics)`
  - `dependency_skills(manifests)`: requirements.txt, pyproject.toml, package.json, go.mod, Cargo.toml
  - `contribution_skills(events)`: commits and PRs to other repos, where available
- Task: `extract_developer_skills`.

**FR-PROFILE-003: Identify interests**
- Build: `interest_extractor` that maps README phrases, repo descriptions and topics to an interest
  taxonomy (AI, developer tooling, web, databases, infra, security, data eng, mobile…) using synonyms.
  `GET /api/v1/profile/interests`.

**FR-PROFILE-004: Evidence per skill**
- Build: `SkillEvidence(developer_skill, source, supporting_repo?, detail, observed_at)`.
  `GET /api/v1/profile/skills` returns skills with their evidence.
- Done when: the UI shows *why* each skill was detected ("8 repositories, dependency usage, README").

**FR-PROFILE-005: Configurable confidence**
- Build: `EVIDENCE_WEIGHTS` in settings (defaults from SRS-1 §15: README 0.20, topic 0.30,
  language 0.50, dependency 0.60, commit 0.80, PR 0.90, repeated contribution 1.00);
  `compute_confidence(evidence) → 0..1`, with diminishing returns so a single README mention stays low.
  Experience level (beginner/intermediate/experienced) comes from several signals and is used
  only for matching.

Frontend: profile page with skill bars labeled by evidence (not "expertise %"), languages chart,
interests, and a refresh button.

### Phase 4 — Repository discovery  → *System builds a candidate pool*  ✅ shipped in v0.4.0

Archived: `openspec/changes/archive/2026-09-29-phase-4-repository-discovery/`. Specs:
`repository-discovery`, `repository-analysis`, `repository-activity` (plus a delta to
`sync-jobs`). Docker verification and the Windows Ctrl+C issue are carried over to Phase 5.

Deviations from the sketch below, as built:
- Provenance is split: one `RepositoryCandidate` per (developer profile, repository) plus
  `CandidateDiscovery` rows (source, query, search rank, first/last seen), so a repository found
  by several queries is one candidate with several sources. Candidates FK `DeveloperProfile` and
  cascade with it.
- The discovery job is `repository_discovery` (task `repositories.generate_candidates`) with
  steps queries → search → interactions → analysis → pool. It starts after every completed sync
  or profile analysis. Analysis is shared across users (`services/repositories/`) and runs
  `DISCOVERY_ANALYSIS_CONCURRENCY` threads; the backlog uses the app's client credentials.
- Eligibility (`is_eligible`, `ineligible_reason`) is stored separately from the lifecycle.
- The pool cap keeps the best candidates in analysis order (interacted, best search rank);
  locally `.env` sets `DISCOVERY_MAX_POOL` and `DISCOVERY_MAX_ANALYSES_PER_RUN` (10 for fast
  runs, 40 for benchmark exports).
- Since `discovery-size-mix`: each query runs once per star band (`DISCOVERY_STAR_BANDS`, the
  budget counts requests; ranks restart per band, so the cap keeps a size mix; job metadata
  `pool_bands`), and lists/docs repositories are rejected or made ineligible as `not_code`.
- Added beyond the FRs: dead-worker recovery (`SyncJob.heartbeat`, `jobs.recover_stale_jobs`,
  `SYNC_STALE_AFTER_SECONDS` 10 min), `REDIS_SOCKET_TIMEOUT`, and a threaded local worker.

**FR-REPO-001: Generate candidates**
- Build: `services/discovery/queries.py` turns top skills and interests into GitHub search queries
  (`language:python topic:django`, `topic:developer-tools language:python`, …), with a budget of
  N queries per run. `GitHubClient.search_repositories(q)`. Task `generate_candidates`.
  Hard filters: not archived, not a fork, pushed within X days, has a license, excludes the user's own repos.

**FR-REPO-002: Record discovery source**
- Build: `RepositoryCandidate(developer, repository, source ∈ {language_search, topic_search,
  skill_search, interest_search, similar_repo, previously_interacted}, query, discovered_at)`.

**FR-REPO-003: Analyze repository metadata**
- Build: tasks `sync_repository`, `sync_repository_readme`; also fetch the CONTRIBUTING, CODE_OF_CONDUCT
  and issue-template presence. Repo lifecycle field:
  `DISCOVERED → FETCHING → ANALYZED → INDEXED → RECOMMENDABLE`, `→ STALE → REFRESHING`, plus `FAILED`.
  (`EMBEDDED` comes in Phase 6.)

**FR-REPO-004: Activity signals**
- Build: `services/matching/activity.py` computes days since the last push, recent commits and PRs,
  contributor count, release recency and open-issue count → `RepositorySnapshot` plus a label
  (`recently_active | moderately_active | low_activity`).
- Periodic Celery beat job marks repos STALE by data type (metadata: hours, README: longer).

### Phase 5 — Recommendation engine (deterministic)  → *Personalized repo recommendations*  ✅ shipped in v0.5.0

Archived: `openspec/changes/archive/2026-09-29-phase-5-recommendation-engine/`. Specs:
`recommendation-engine`, `recommendation-explanations`, `recommendations-view` (plus a delta to
`sync-jobs`). The Windows Ctrl+C issue is carried over to Phase 8a; Docker Compose verification
moved to future scope.

Deviations from the sketch below, as built:
- Signal keys are `skill`, `language`, `interest`, `framework`, `activity`, `openness`; per-signal
  values live in `Recommendation.signal_scores` (JSON), not one column per signal.
- `ScoringConfig` also stores `params` (bands, activity values, openness points, technology
  source weights) and `description`; a partial unique constraint keeps one config active.
- Relevance gate: a candidate needs a skill, language, framework or interest match above 0;
  activity and openness alone never make a recommendation (found while implementing).
- Recommendations are upserted per (developer, repository), so ids survive regenerations; no
  history is kept. `technologies`, `activity_label` (blank when unknown) and `size` (contributor
  thresholds) are stored on the row for filters.
- Reason types are `skill, language, framework, interest, activity, openness`; `domain`,
  `difficulty` and `issue_availability` wait for Phases 6–7.
- There is no separate `refresh_recommendations` trigger per change: the beat task sweeps every
  30 minutes. The API exposes no score or rank. Filters show only past one page (20) or when
  active. Save lives in Phase 8a.

**FR-REC-001: Calculate relevance**
- Build: signal calculators in `services/matching/`, each returning `(score 0..1, evidence[])`:
  `skill_match`, `language_match`, `framework_match`, `interest_match` (taxonomy overlap),
  `activity_signal`, `contribution_openness` (CONTRIBUTING present, good-first-issue label exists).

**FR-REC-004: Configurable weights**
- Build: `ScoringConfig(version, weights JSON, is_active, created_at)`. Seed `v1-deterministic`
  (experimental): skill 0.40, language 0.20, interest 0.15, framework 0.10, activity 0.10,
  openness 0.05.

**FR-REC-002: Rank candidates**
- Build: `services/ranking/score.py` computes a weighted sum → `Recommendation(developer, repository,
  score, per-signal scores, scoring_config, generated_at)`. Keep the top N (≥ 20).
  Tasks `generate_recommendations`, `refresh_recommendations` (run on profile change or repo change).

**FR-REC-005: Record the scoring config**
- Done when: every Recommendation has a non-null FK to the ScoringConfig that produced it.

**FR-REC-003: Explanations**
- Build: `services/ranking/explain.py` turns signal evidence into
  `RecommendationReason(recommendation, type ∈ {skill, language, framework, interest, domain,
  activity, difficulty, issue_availability}, text, weight)`. Only reasons backed by a
  non-zero signal are created. Match label comes from score bands (Strong/Good/Partial).

**FR-REC-006: Filtering**
- Build: `GET /api/v1/recommendations?language=&framework=&activity=&size=&page=` (django-filter);
  `GET /api/v1/recommendations/{id}`. Difficulty and contribution-type filters are added in Phase 7.

Frontend: dashboard (profile summary, recommendation cards with name, owner, description,
technologies, match label, reasons, activity, save, GitHub link), filters, repository detail page
(overview, why it matches, technologies, topics, activity, contribution guidelines, README excerpt,
GitHub link).

### Phase 8a — Feedback and data controls (MVP)  ✅ shipped in v0.6.0

Archived: `openspec/changes/archive/2026-10-01-phase-8a-feedback-data-controls/`. Specs:
`recommendation-feedback`, `data-controls` (plus a delta to `github-authentication`). The Ctrl+C
carry-over is closed (§6 Known issues). No carry-overs; Docker Compose verification stays future
scope. **The MVP definition of done is met.**

Deviations from the sketch below, as built:
- Save and dismiss state live in their own tables in the new `feedback` app
  (`SavedRepository`, `DismissedRepository`), not in `recommendations/`. The event log is
  append-only history; it is not used to derive current state.
- Feedback actions also include `unsaved` and `undismissed`. Each event snapshots
  `repository_full_name`, `match_label`, `rank` and `config_version`; repository and
  recommendation FKs are `SET_NULL`, so events survive regenerations and deletions. `viewed` is
  de-duplicated within `FEEDBACK_VIEW_DEDUP_MINUTES` (30).
- Dismiss deletes the recommendation row and any save; `RecommendationService._persist` re-checks
  dismissals inside its transaction. Restore (`DELETE /dismissed/{repository_id}`) starts a
  generation, which brings the project back.
- One deletion routine (`services/data_deletion.py`) serves delete-data, disconnect and account
  deletion. It also removes orphaned shared repositories and purges the user's GitHub response
  cache (`github:etag:{pk}:*`, `github:ratelimit:{pk}`). Disconnect deleting data is a behavior
  change. Audit entries lose their user link (`SET_NULL`) when the account is deleted.
- FR-DATA-002 needed no backend change: the dashboard shows the running stage
  (`usePipelineStage`) next to Refresh.
- Frontend pitfalls found in manual testing: a mutation started from a component that the
  optimistic update unmounts must use `mutateAsync` (per-call `mutate` callbacks are skipped after
  unmount); a short generation can finish between two status polls, so the list refreshes on any
  newly seen finished job.

**FR-FEEDBACK-001: Record views** · **FR-FEEDBACK-004: Repo/issue interactions**
- Build: `RecommendationFeedback(user, recommendation, action ∈ {viewed, saved, dismissed,
  opened_repository, opened_issue}, created_at)`; `POST /api/v1/recommendations/{id}/feedback`.
  Stored independently from the recommendation; used for analytics only (no ranking changes yet).

**FR-FEEDBACK-002: Save** · **FR-FEEDBACK-003: Dismiss**
- Build: `SavedRepository(user, repository, saved_at)`; saved list page; dismissed repos are
  excluded from later ranking runs.

**FR-DATA-002: Refresh profile**: the refresh button triggers the Phase 2→5 pipeline with SyncJob tracking.

**FR-DATA-003: Delete data**
- Build: `DELETE /api/v1/profile/github-data`, `DELETE /api/v1/auth/account`; disconnect flow
  = revoke token → delete GitHub-derived data → keep only account essentials. Privacy page
  lists what is stored. Audit-log these actions.

### MVP definition of done (SRS-2 §82)  ✅ met in v0.6.0

Sign in with GitHub · public profile analyzed · profile README analyzed when present ·
see skills with evidence, interests, and languages · ≥ 10 repository recommendations with
reasons · open on GitHub · filter · save · refresh · see last-synced time · disconnect/delete data.

### MVP+ / future

**Phase 6 — Semantic matching** (future; AI provider not chosen)
- `services/ai/` interfaces: `EmbeddingProvider.embed(texts)`, `LLMProvider.extract(schema, text)`
  with Pydantic validation. Embedding dimension comes from settings.
- Developer, repository and issue embeddings (pgvector), `semantic_match` signal, `EMBEDDED` lifecycle
  state, a new ScoringConfig version that includes semantic weight. Tasks `generate_*_embedding(s)`.
- AI failures fall back to deterministic scoring.

**Phase 7 — Issues** (MVP+)  ✅ shipped in v0.7.0

Archived: `openspec/changes/archive/2026-10-13-phase-7-issues/`. Specs: `issue-ingestion`,
`issue-analysis`, `issue-matching` (plus deltas to `repository-analysis`, `recommendation-engine`,
`recommendation-explanations`, `recommendations-view`, `recommendation-feedback`). No carry-overs;
Docker Compose verification stays future scope.

Deviations from the sketch below, as built:
- The client method is `list_open_issues` (one page of 100 most recently updated, PRs dropped,
  410 = none). Issues are an analysis part (`REPO_STALE_AFTER["issues"]`, 6 h); the backlog
  queues `repositories.sync_repository_issues` when only issues are stale. No separate
  `github:issues:*` cache key: the ETag cache covers it.
- Analysis lives on the `Issue` row (canonical labels, type, difficulty, technologies, evidence)
  and is recomputed on every fetch. Difficulty is a vote: a level needs 2 agreeing signals and
  no contradiction. Two or more technologies vote intermediate (otherwise intermediate could
  never win); an empty body or no technology abstains. HTML/CSS are not issue technologies, and
  `bug` is a title keyword for `[Bug]:` prefixes (both found in manual testing).
- Issue matching runs inside generation for candidates past the relevance gate (one query) and
  feeds the `issue_fit` and `difficulty_fit` signals. All numbers, including approachability
  values, are `params.issues` of the new active config `v2-deterministic`. Stored configs are
  validated with `stored=True`, so v1 (no issue signals) still scores, with issue weights 0.
- `Recommendation` stores `relevant_issue_count`, `issue_difficulties` and
  `issue_contribution_types` snapshots for the filters. `RecommendedIssue.reasons` is JSON, not
  `RecommendationReason` rows. Persist locks the matched issues and drops any deleted meanwhile.
- `issues.Difficulty` is `developers.IssueDifficulty` (one OpenAPI `DifficultyEnum`).
- `opened_issue` feedback requires `issue_id` of one of the recommendation's relevant issues and
  stores `issue` (`SET_NULL`) plus `issue_number`.

Sketch:
- FR-ISSUE-001: `GitHubClient.get_issues`, task `sync_repository_issues`, `Issue` model.
- FR-ISSUE-002: label normalization (good first issue, help wanted, docs, bug, enhancement, …).
- FR-ISSUE-003: contribution type (label and keyword rules first).
- FR-ISSUE-004: difficulty ∈ {beginner, intermediate, advanced, unknown}; default `unknown`.
- FR-ISSUE-005: issue match signals, reasons, and an issue detail page that separates GitHub-provided
  data from ContribFinder analysis; add difficulty and contribution-type filters.

**Phase 8b — Evaluation** (MVP+)  ✅ shipped in v0.8.0

Archived: `openspec/changes/archive/2026-10-14-phase-8b-evaluation/`. Spec:
`recommendation-evaluation`. No carry-overs; Docker Compose verification stays future scope.

Deviations from the sketch below, as built:
- Evaluation is offline (management commands, no API, model or UI) and ranks through
  `services/ranking/pipeline.rank_pool`, which generation now calls too, so the two cannot drift.
- The seed benchmark `benchmark-v1` is six persona developers over 40 fictional `bench/`
  repositories, judged from the persona descriptions before any run; real developers can be
  added with `export_benchmark_developer` (anonymized, unjudged) and judged by hand.
- Improvement rule: NDCG@10 strictly higher and no other metric lower by more than 0.01.
  `baselines.json` pins min score 0.10 and top N 50 so a local `.env` cannot change CI's numbers.
- Result on `benchmark-v1`: v2 is **not** an improvement over v1 (NDCG@10 +0.0195, P@5 −0.0333).
  v2 stays active; tuning is left to a later change, which must win on the benchmark.

Sketch:
- Fixed benchmark developers with hand-labeled relevant repos; compute Precision@5/10,
  Recall@10, MRR and NDCG per ScoringConfig. A ranking change counts as an improvement only if it wins here.

**Ranking experiment — v3 candidates** (MVP+)  ✅ shipped in v0.9.0 (no ranking change)

Archived: `openspec/changes/archive/2026-10-14-ranking-v3-deterministic/` (results in
`candidates/RESULTS.md`). Specs: deltas to `recommendation-engine` and `recommendation-evaluation`.
- Added `holdout-v1` (acceptance only) and the replacement rule; optional parameters
  `issues.difficulty_fit_mode` (`best`/`weighted`) and `relevance_scaling`, off in v1/v2.
- 15 predeclared candidates; none beat both v1 and v2 on `benchmark-v1`, so no v3 was seeded and v2
  stays active. Relevance scaling fixed the off-topic top-5 problem but pushed weak relevant
  repositories under the global `RECOMMENDATION_MIN_SCORE`.
- Carry-over: closed by the next experiment below (its diagnosis also corrects this one's).

**Ranking experiment — configuration minimum score** (MVP+)  ✅ shipped in v0.10.0 (no ranking change)

Archived: `openspec/changes/archive/2026-10-14-ranking-min-score-config/` (results in
`candidates/RESULTS.md`). Specs: deltas to `recommendation-engine` and `recommendation-evaluation`.
- Added `params.min_score` / `min_score_basis` (`score` | `relevance`; absent = setting),
  `evaluate_ranking --min-score` as override, `baselines.json` format 2, fresh `holdout-v2` and the
  rule that a seen holdout cannot accept a later search (next search adds `holdout-v3`).
- 16 candidates; none qualified on `benchmark-v1` and each matched its v3 base exactly: the minimum
  score was never the constraint. The repositories relevance scaling drops for dev-beginner have a
  relevance part near 0.008 and are judged 1; both holdouts favor the candidates.
- Carry-over: closed in part by the change below (tooling shipped; judging carried over).

**Benchmark tooling — real developers** (MVP+)  ✅ shipped in v0.11.0 (no ranking change)

Archived: `openspec/changes/archive/2026-10-14-benchmark-real-judgments/`. Spec: delta to
`recommendation-evaluation`.
- Developer `kind` (`persona` | `real`) with persona/real means in reports; `benchmark_sheet`
  (blind CSV), `import_judgments`, `build_benchmark`; `selection_dataset()` picks `benchmark-v2`
  once it holds a judged real developer, else `benchmark-v1`; `baselines.json` format 3 (by dataset).
- Exports and sheets live in the gitignored repo-root `judging/` (`../../judging/...` from
  `apps/backend`, where `npm run manage` runs); commands create output folders.
- Carry-over 1 (discovery bias): closed by `discovery-size-mix` below.
- Carry-over 2: re-export `real-a`, judge every row, import, build `benchmark-v2`, evaluate
  v1/v2 (all/persona/real) and `--write-baseline` for it, before any further ranking search.
  Still open after v0.12.0 (the re-export is done, see below).

**Discovery project-size mix** (MVP+)  ✅ shipped in v0.12.0 (no ranking change)

Archived: `openspec/changes/archive/2026-10-15-discovery-size-mix/`. Spec: delta to
`repository-discovery`.
- Star bands per query (`DISCOVERY_STAR_BANDS`, default `20..999` and `1000+`, validated by a
  system check); `DISCOVERY_MAX_QUERIES` counts requests (default 20); job metadata `pool_bands`.
- `not_code` rejects or makes ineligible lists and docs repositories (`awesome-*` names,
  `DISCOVERY_EXCLUDED_TOPICS`, no primary language); the pool step re-checks stored data
  (`pool_not_code`), since fresh analyses skip eligibility.
- Re-export `judging/real-a-v2.json` (40 candidates): median contributors 906 → 56.5, under 50
  2/39 → 19/40. Docs-style repositories with a code language (`system-design-primer`) still pass.
- Carry-over: judge `real-a-v2` (benchmark-tooling carry-over 2 above) before any ranking search.

**Security hardening** (MVP+, fix release)  ✅ shipped in v0.12.1 (no ranking change)

Archived: `openspec/changes/archive/2026-10-19-security-hardening/`. Specs: deltas to
`api-platform`, `github-authentication`. Batch 1 of `Bug_Backlog.md` (repo root: the verified
codebase sweep of 2026-10-19, 147 findings in 11 fix batches).
- `NUM_PROXIES` (default 0; `.env.example` 1 for the Vite proxy) is the only trust switch for
  forwarded headers: DRF throttles, `services.audit.client_ip` (DRF's `get_ident`, so audit and
  throttling share one rule) and `SECURE_PROXY_SSL_HEADER`.
  Check `core.W002` warns on SSL redirect with no trusted proxy.
- `core.startup.run_startup_checks()` runs from `wsgi.py` and Celery `worker_init`/`beat_init` when
  `RUN_STARTUP_CHECKS` (production only). `config/celery.py` now defaults to production settings;
  the npm runners set development (`loadEnv()` in `scripts/env.mjs`), the image sets production.
- OAuth states: session key `github_oauth_states` (`{state: issued_at}`),
  `OAUTH_STATE_MAX_PENDING` 5, `OAUTH_STATE_TTL_SECONDS` 600.
- Carry-over: closed by batch 2 below (E-3); batch 3 (evaluation tooling) still precedes judging.

**Privacy and deletion finality** (MVP+, fix release)  ✅ shipped in v0.12.2 (no ranking change)

Archived: `openspec/changes/archive/2026-10-19-privacy-deletion-finality/`. Specs: deltas to
`data-controls`, `github-authentication`, `recommendation-evaluation`. Batch 2 of `Bug_Backlog.md`.
- `services/job_guard.py`: `job_write(job_id)` (transaction + `SELECT … FOR UPDATE` on the job,
  `JobCancelled` unless RUNNING) wraps every job write of user data; `save_progress(job, **fields)`
  stores steps/metadata only while RUNNING. Deletion cancels jobs first, so it waits for an
  in-flight write and later writes see the cancel. `JobCancelled` lives in `services/errors.py`.
  New job services must use both, and fetch before entering `job_write` (never I/O under the lock).
- `ProfileAnalysisService(user, job_id=...)`; without a job id it writes unguarded (tests only).
- Disconnect rotates the unusable password (ends every session); delete-data clears
  `display_name`; account deletion runs `audit.anonymize_user_entries`.
- Re-sign-in with a new token queues `github.revoke_replaced_token` (encrypted old token only,
  single-token revoke via `oauth.revoke_token`); the task re-checks the stored token.
- `export_benchmark_developer` drops interacted repositories unless `--include-interacted`.
- Carry-over: closed by batch 3 below.

**Evaluation tooling integrity** (MVP+, fix release)  ✅ shipped in v0.12.3 (no ranking change)

Archived: `openspec/changes/archive/2026-10-19-evaluation-tooling-integrity/`. Spec: delta to
`recommendation-evaluation`. Batch 3 of `Bug_Backlog.md`.
- `baselines.json` format 4 (`top_n` per dataset; `baseline.top_n(data, dataset)` reads 1–4).
  `baseline.write` merges per config and raises `BaselineError` before writing when a different
  top N leaves a recorded config out. `baseline.default_datasets()` is what `--write-baseline`
  rewrites without `--dataset`: `benchmark-v1`, recorded datasets with files, and `benchmark-v2`
  once it is the selection benchmark. `--min-score` with `--write-baseline` is refused.
- `read_sheet` skips `#` lines only above the header and parses the rest as one CSV stream;
  all-blank rows are ignored, repeated repositories and grades without a repository fail naming
  the CSV line. `import_sheet` sets `sheet.JUDGED` as developer and export description.
- `build` rejects inputs that are not `dict` with `format == FORMAT`.
- Write the first `benchmark-v2` baseline without `--config`: a new dataset entry holds only the
  configs evaluated, and the baseline test requires v1 and v2.
- Carry-over: judge `real-a-v2` (K-1), build `benchmark-v2`, evaluate v1/v2 and write its
  baseline, before any further ranking search.

**Job lifecycle and claim fencing** (MVP+, fix release)  ✅ shipped in v0.12.4 (no ranking change)

Archived: `openspec/changes/archive/2026-10-19-job-claim-fencing/`. Specs: deltas to `sync-jobs`,
`repository-analysis`, `developer-profile`. Batch 4 of `Bug_Backlog.md`.
- `claim_job(job_id) -> SyncJob | None` sets `SyncJob.claim_token`; `job_write(job)`,
  `save_progress(job)`, `job_guard.heartbeat(job)` (replaces `SyncJob.heartbeat()`) and
  `finish_job(job, ...)` match status RUNNING and the token, so a reclaimed worker gets
  `JobCancelled` and starts no follow-up. Pass the claimed job object, never an id.
- Every terminal transition goes through `_end_jobs`: it clears the token and turns `running`
  steps `failed`. All four `start_*` go through `_start_job(user, job_type)`, which builds the
  steps from `STEPS_BY_JOB_TYPE`. `job_guard.stale_before(now)` is the one stale cutoff (jobs
  and repository claims); `_stale_running(now)` the one dead-worker filter. Recovery moves dead
  RUNNING jobs to RETRYING and requeues PENDING/RETRYING jobs idle for
  `SYNC_STALE_AFTER_SECONDS + GITHUB_MAX_RETRY_DELAY` (`_requeue`).
- With `CELERY_TASK_ALWAYS_EAGER`, `run_tracked_job` decides as on the last attempt (no inline
  retry); tests of the retry path use `override_settings(CELERY_TASK_ALWAYS_EAGER=False)`.
- Repository claims: `claim_token` and `claimed_at` (claim age) on `Repository`; claim and
  release leave `lifecycle_changed_at` alone. `lifecycle.renew/hold/release/fail/complete` match
  the token and raise or no-op on `ClaimLost`; analysis returns `SKIPPED` when reclaimed.
- `ProfileAnalysisService(user, job=...)` drops a result older than the stored `analyzed_at`.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**GitHub error resilience** (MVP+, fix release)  ✅ shipped in v0.12.5 (no ranking change)

Archived: `openspec/changes/archive/2026-10-21-github-error-resilience/`. Specs: deltas to
`github-data-sync`, `repository-analysis`, `github-authentication`, `api-platform`. Batch 5 of
`Bug_Backlog.md`.
- `GitHubClient`: a 403/429 whose message says secondary rate limit (or abuse detection), with no
  `Retry-After`, is `GitHubRateLimited(SECONDARY_LIMIT_DEFAULT_WAIT = 60)`. Redirects are followed
  up to `MAX_REDIRECTS = 3`, API origin only (scheme, host, port; else `GitHubClientError`); the
  ETag key stays the original URL. `for_user` turns `TokenDecryptionError` into `GitHubAuthError`.
  Public client methods (`@_parses_response`) raise `GitHubInvalidResponse` (a
  `GitHubClientError`) for a body that is not the expected JSON; callers never catch bare
  `KeyError`/`ValueError` for GitHub data.
- Sync: languages skip a repository on `SKIPPABLE` errors (metadata `languages_skipped`), the
  profile README step returns `skipped`, topics are stored by the repositories step (the topics
  step only marks progress), and the profile step also updates
  `GitHubAccount.username`/`avatar_url`. `fetch_identity` validates the payload
  (`identity_failed`, login must be a non-empty string). `parse_manifest` catches
  `RecursionError`.
- Repository analysis: ordered `ERROR_CODES` (`GitHubInvalidResponse` → `invalid_response`,
  `GitHubClientError` → `client_error` after its subclasses). Everything else still releases
  and re-raises.
- Refresh failures (also rejected app credentials): `lifecycle.record_refresh_failure(repo_id,
  code, since=started)` sets `lifecycle_error` and `Repository.refresh_failed_at` without
  changing state, skipping rows whose `lifecycle_changed_at >= since`; the backlog delays only
  STALE/DISCOVERED rows for `REPO_REFRESH_RETRY_MINUTES` (60); `complete`/`fail` clear it.
- Redis off the request path: `core/throttling.py` throttles count in a per-process
  `LocMemCache` after a cache error (`THROTTLE_CACHE_BACKOFF_SECONDS`, 30) and `SESSION_ENGINE`
  `db`. Worker-side ETag cache behavior without Redis is batch 11 (A-16).
- Review follow-ups V-1…V-7 and V-9 of `Bug_Backlog.md` are fixed in the same release (V-8 wontfix).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Recommendation consistency** (MVP+, fix release)  ✅ shipped in v0.12.6 (no ranking change)

Archived: `openspec/changes/archive/2026-10-21-recommendation-consistency/`. Specs: deltas to
`recommendation-engine`, `recommendation-feedback`, `recommendation-evaluation`. Batch 6 of
`Bug_Backlog.md`.
- Scorable = `is_eligible` and `lifecycle.SCORABLE` (RECOMMENDABLE, STALE, REFRESHING): marking
  stale and claiming keep `is_eligible`. `load_candidates(profile, include_dismissed=False)`;
  the export passes `True`.
- Lock order (`services/locks.py`): job (`job_write`) → `lock_developer(user_id)` (profile row
  `select_for_update`) → dismissals/saves → recommendations → issues by pk → children. Save,
  unsave, dismiss, restore, `_persist` and `delete_github_data` lock the profile first;
  `record` locks only its recommendation row (skips when it is gone); `_store_issues` locks all
  issues it touches by pk first. New writers of recommendation or feedback rows must follow
  it. Events never reference a recommendation that may be gone (deferred FK fails at commit).
- Generation ranks uncut (`rank_pool(top_n=None)`); `_persist` drops dismissals, then cuts to
  `RECOMMENDATIONS_TOP_N`. A matched issue missing or re-analyzed (`IssueFeature.analyzed_at`)
  under the lock raises `IssuesChanged`; `run()` loads candidates once and re-ranks up to
  `MAX_ATTEMPTS = 3`, then `issues_changed`.
- `SyncJob.rerun_requested`: `start_recommendations` sets it on a RUNNING generation (a new
  job if it finished meanwhile) unless `rerun_if_running=False`;
  `rerun_recommendations_if_requested` is the task's `on_completed` hook; `claim_job` clears it.
- Freshness: `pool_changed` ignores STALE/REFRESHING repositories, `data_changed` takes the
  latest data time (`staleness.PART_FIELDS`, the one part → `*_synced_at` map); profiles with
  recommendations and no candidates are due; a failure within
  `RECOMMENDATION_FAILED_RETRY_MINUTES` (360) is not; the sweep starts with
  `rerun_if_running=False`, so an active generation is left alone.
- Feedback: save re-checks the recommendation and the dismissal under the lock
  (`Recommendation.DoesNotExist` → 404); dismiss records `unsaved`.
- Review follow-ups W-1…W-10 of `Bug_Backlog.md` fixed in the same release; main specs updated
  directly (the archived deltas predate them).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Future scope**: verify `docker compose up` from a fresh `.env` (needs a machine with Docker).

**Post-MVP**: personalized or feedback-based ranking, notifications, contribution tracking,
contribution plans, similar repositories, observability dashboards (Sentry, Prometheus, Grafana).

**Ideas** (`ideas.md`, gap analysis 2026-10-20, unplanned): IDF weighting, time decay on skill
evidence, top-k diversity, stated preferences, contribution-success signals (maintainer
responsiveness, linked PRs), evaluation rigor (bootstrap CIs, inter-rater agreement, discovery
recall), online report per config from feedback, dismiss reasons, CSP, dependency scanning.
Ranking-visible ideas wait for K-1; bootstrap CIs should land before or with it.

## 8. Release housekeeping

When a change (phase) is completed and archived, update in the same commit:
1. `VERSION`, root `package.json`, `apps/frontend/package.json`, `apps/backend/pyproject.toml`
   (then refresh lockfiles: `npm install` / `uv lock`). Before the MVP, each phase bumps the minor
   version (`0.x.0`), and fixes bump the patch version. `npm run check:version` must pass (it also
   checks `package-lock.json`, `apps/frontend/package-lock.json` and `apps/backend/uv.lock`).
2. `CHANGELOG.md`: move `[Unreleased]` entries into a dated version section (Keep a Changelog).
3. `features.txt`: flip shipped items to `[x]`, and mark carry-overs `[~]`.
4. `README.md`: version/status line, plus any setup changes.
5. This file: mark the phase shipped, and record carry-overs in the next phase.

The API contract version (`/api/v1`, OpenAPI `1.0.0`) changes only on breaking API changes,
independently of the app version.
