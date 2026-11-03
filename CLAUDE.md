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
- Both SRS files are kept locally and gitignored (untracked in 0.12.39, before the repository
  went public); a checkout without them still has `openspec/specs/` and this file.
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
│  │  │                     startup (production check gate), throttling (cache-outage fallback),
│  │  │                     backoff (per-process skip after a cache error), csp (Content-Security-
│  │  │                     Policy middleware), reports (JSON files written by commands), admin (NoAddDeleteAdmin, ViewOnlyAdmin)
│  │  ├─ accounts/          User, AuditEvent, auth views, session, data deletion
│  │  ├─ github/            GitHubAccount, GitHubProfile, sync task (tasks.py), profile API
│  │  ├─ jobs/              SyncJob (generic tracked jobs), sync status and data versions API,
│  │  │                     recover_stale_jobs task
│  │  ├─ developers/        DeveloperProfile, Skill, DeveloperSkill, SkillEvidence, Interest,
│  │  │                     DeveloperInterest, InterestEvidence; profile API; analysis task;
│  │  │                     reanalyze_profiles command
│  │  ├─ repositories/      Repository (lifecycle, eligibility), RepositoryLanguage, RepositoryTopic,
│  │  │                     RepositoryDependency, UserRepository (owner | contributor),
│  │  │                     RepositoryReadme, RepositorySnapshot, RepositoryCandidate,
│  │  │                     CandidateDiscovery; discovery API; discovery/refresh/beat tasks;
│  │  │                     queries.py (latest_snapshot prefetch); discovery_report command
│  │  ├─ issues/            Issue (shared, analysis on the row), RecommendedIssue; issue
│  │  │                     detail API (Phase 7)
│  │  ├─ recommendations/   ScoringConfig, Recommendation, RecommendationReason; API; generation
│  │  │                     and freshness tasks; evaluate_ranking, export_benchmark_developer,
│  │  │                     benchmark_sheet, import_judgments, build_benchmark commands;
│  │  │                     migrations/_seeding.py (frozen helpers: later seeds stored inactive)
│  │  ├─ feedback/          RecommendationFeedback, SavedRepository, DismissedRepository; feedback,
│  │  │                     saved and dismissed API (Phase 8a)
│  │  ├─ e2e/               e2e_seed command (browser-test users and sessions), builders.py (seed
│  │  │                     builders, also re-exported to tests; imports nothing from tests/);
│  │  │                     installed only by config/settings/e2e.py, never in production
│  │  ├─ embeddings/        (Phase 6, future)
│  │  ├─ evaluation/        data only: benchmark-v1.json (seed benchmark), holdout-v1.json and
│  │  │                     holdout-v2.json (acceptance only, never for choosing; both used, so
│  │  │                     the next search adds holdout-v3), benchmark-v2.json (personas plus
│  │  │                     judged real developers; selection benchmark once it exists),
│  │  │                     baselines.json (format 4, keyed by dataset, top N each)
│  │  └─ services/          crypto.py (token encryption), audit.py, jobs.py (start/claim/finish
│  │     │                  jobs), errors.py (PermanentJobError, JobCancelled), job_guard.py
│  │     │                  (stale_before, lost_before, job_write, save_progress, merge_metadata,
│  │     │                  heartbeat),
│  │     │                  locks.py (lock_developer: one lock order for recommendations and
│  │     │                  feedback), feedback.py (record, save, dismiss, restore), text.py
│  │     │                  (join_names),
│  │     │                  data_deletion.py (GitHub data / account deletion), data_versions.py
│  │     │                  (when each derived data area last changed)
│  │     ├─ github/         oauth.py, accounts.py; GitHubClient, GitHubSyncService (Phase 2),
│  │     │                  storage.py (shared repository upserts, lock_repository), errors.py
│  │     │                  (typed errors, API_VERSION, error_for_response)
│  │     ├─ profiling/      taxonomy, manifests, readme/collectors, confidence, interests,
│  │     │                  experience, summary, analysis (Phase 3)
│  │     ├─ discovery/      queries, filters (prefilter/eligibility), ordering (pool order),
│  │     │                  DiscoveryService (Phase 4), yield_report (search yield per strategy
│  │     │                  and band)
│  │     ├─ repositories/   analysis, lifecycle, staleness, backlog (shared repository data,
│  │     │                  Phase 4), setup (setup facts from the root listing; shown, never scored)
│  │     ├─ issues/         labels (normalization), classify (type, difficulty),
│  │     │                  technologies, analysis (Phase 7)
│  │     ├─ matching/       activity, technologies, features (loading), signals,
│  │     │                  issues (issue matching) (Phase 4–7)
│  │     ├─ ranking/        config (validation), pipeline (rank_pool, shared by generation and
│  │     │                  evaluation), score, explain, service (generation), freshness (Phase 5),
│  │     │                  activation (activate_scoring_config; the admin shows the command)
│  │     ├─ evaluation/     dataset (benchmark load/validate, selection_dataset), metrics, runner
│  │     │                  (evaluate, compare, persona/real subsets), baseline, export, sheet
│  │     │                  (blind judging sheets), build (merge datasets) (Phase 8b+),
│  │     │                  bootstrap (paired intervals), feedback_report (outcomes per config)
│  │     └─ ai/             provider interfaces only (future)
│  └─ frontend/           src/{app,components,features,hooks,lib,api,types,routes}; components/
│                         holds DeadEnd, ExternalLink, Fact, Loaded; lib/ format (dates); app/ holds
│                         the query client (retry, stale time, 401), session.ts (identity key,
│                         endSession, leaveSignedIn), job-transition refresh and data versions;
│                         e2e/ Playwright specs, playwright.config.ts; csp.config.ts (the built
│                         app's Content-Security-Policy and its build-only Vite plugin)
├─ scripts/                 npm runners: start, stop, setup, backend, frontend, worker, beat,
│                           redis (WSL), child (process-tree runner, .run/ records), stack
│                           (stop matching), env, wait-port, uv, manage, check-version,
│                           restarts (keep-alive restart budget), e2e-backend (seed + Django for
│                           Playwright), audit (dependency audit); *.test.mjs (node --test)
├─ package.json             root runner: npm run setup / npm start / stop / manage / check:version
│                           / lint:scripts / format:scripts / audit:deps; audit-accepted.json
│                           (accepted advisories); eslint.config.mjs (scripts only),
│                           .prettierrc.json (shared with apps/frontend), .gitattributes (LF)
├─ docker-compose.yml       backend, worker, beat, postgres, redis, frontend
├─ LICENSE (MIT), SECURITY.md (private vulnerability reporting)
├─ VERSION, CHANGELOG.md, features.txt, Bug_Backlog.md (verified findings, fix batches),
│  ideas.md (unplanned gap analysis by when it can ship: no ranking change first, then
│  ranking-visible ideas; each idea needs an OpenSpec change first); reports/ (gitignored --json
│  outputs)
└─ .github/workflows/ci.yml, audit.yml (dependency audit: PRs, main, weekly, on demand)
```

## 5. Conventions

- Business logic lives in `services/`. Views, serializers and Celery tasks are thin
  wrappers that call services.
- Only `services/github/` talks to GitHub. It handles pagination, ETag conditional requests,
  timeouts, retries with exponential backoff, `Retry-After`/secondary rate limits, and
  Redis caching (`github:user:{u}`, `github:repo:{o}:{r}`, `github:issues:{o}:{r}`).
  The ETag cache only saves requests: a cache error makes the request unconditional and the
  process skips the cache for `GITHUB_CACHE_BACKOFF_SECONDS` (`core/backoff.py`); a 304 renews
  the entry. The rest of the app sees normalized dataclasses, never raw GitHub JSON.
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
  `npm run stop` from a second prompt works too. It kills this repo's stack only: runners record
  themselves in the gitignored `.run/` (`recordProcess` in `child.mjs`; `redis.mjs` also records
  the `wsl.exe` keep-alive), and `stop.mjs` (`matchStack` in `scripts/stack.mjs`) kills a record
  only while its live process has the recorded executable and command line, plus this repo's
  Python/Celery and Vite by path; stale records are deleted (and pruned by `start.mjs`). Closing
  the console (SIGHUP) stops every runner, keep-alive included. Beat's schedule file is
  `contribfinder-celerybeat-<sha1(root)[:8]>` (`scheduleFile` in `env.mjs`) in the OS temp dir, one per checkout.
  The SPA proxies `/api`.
- `npm run test:scripts`: Node built-in tests for the runners (`scripts/*.test.mjs`, also in CI).
  `npm run lint:scripts` / `format:scripts`: ESLint and Prettier for `scripts/` (also in CI).
  `.gitattributes` keeps LF in every checkout; a Windows checkout from before 0.12.11 refreshes
  its working files once (README).
  `npm run setup` uses `npm ci` (never rewrites a lockfile); `npm run check:version` also checks
  `packages[""].version` of both npm lockfiles.
- `npm run audit:deps` (`scripts/audit.mjs`, CI workflow `audit.yml`): `pip-audit` (pinned,
  through `uv tool run` on `uv export --frozen`) and `npm audit` for `apps/frontend` and the
  root. Fails on any Python advisory and npm high/critical, unless accepted in
  `audit-accepted.json` (ecosystem, id, package, reason, accepted_on; strict). Exit 0/1/2
  (clean / findings / could not run). The user's npm has `allow-remote=none`: a frontend
  `npm install`/`ci`/`audit fix` needs `--allow-remote=all`, which only the user runs.
- Redis: on Windows, `npm start` starts the `redis-server` service in WSL Ubuntu and keeps the
  distro awake (`scripts/redis.mjs`; a keep-alive that ends is restarted, at most 3 times in 5
  minutes, and logged with its exit code in hex), then a Celery worker with `--pool=threads --concurrency=4`
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
  `--min-score` overrides it. Each candidate also gets a paired bootstrap block (95% interval per
  metric over developers, `*` when it excludes 0; `--resamples`, `--seed`, JSON `comparisons`):
  information only, the improvement rule ignores it (since 0.12.19).
- `npm run manage -- activate_scoring_config <version> [--force --reason "..."]` is the one way
  to switch the active config (`services/ranking/activation.py`; the admin has no activation
  action since 0.12.18, its change page shows this command): refused unless an improvement over
  the active one on the selection benchmark (pinned baseline min score and top N), audited
  (`scoring_config_activated`, `via: "command"`). It does not read a holdout.
- `npm run manage -- feedback_report [--since DAYS] [--config V] [--minimum N] [--json OUT]`
  reports feedback events per config version and rank bucket: positive share (saved + opened out
  of those + dismissed), a position-adjusted share, per-label rows and a calibration verdict
  (0.12.21). Aggregates only, read-only (0.12.20). `--json` outputs go in the gitignored
  `reports/` (`../../reports/...` from `apps/backend`).
- `npm run manage -- discovery_report [--since DAYS] [--json OUT]` (0.12.25): discovery search
  yield per strategy, star band and both, from finished runs' `query_yield`. Aggregates only,
  read-only; use it before changing queries, shares, bands or the budget.
- Real judged developers (README "Judging real developers"): `export_benchmark_developer` →
  `benchmark_sheet` (blind CSV) → `import_judgments` → `build_benchmark`. `evaluate_ranking`
  defaults to the selection benchmark: `benchmark-v2` once it holds a `real` developer, else
  `benchmark-v1`. Exports and sheets go in the gitignored `judging/` (paths `../../judging/...`,
  since commands run in `apps/backend`); committing `benchmark-v2` is the judge's call.

Docker (kept, not used here): `docker compose up --build`. Compose overrides `DATABASE_URL` /
`REDIS_URL` with container hostnames; Postgres is on host port 5433.

Backend (`apps/backend`, uses `uv`):
- `uv sync`: install deps
- `uv run pytest`: tests. Uses `config.settings.test` against local PostgreSQL (creates `test_contribfinder`);
  of `.env` only `DATABASE_URL` is read (`DJANGO_READ_DOTENV=DATABASE_URL`, since 0.12.39)
- `uv run ruff check . && uv run ruff format --check .`: lint and format
- `uv run mypy .`: strict type check
- `uv run python manage.py makemigrations --settings config.settings.test`: new migrations

Frontend (`apps/frontend`, npm):
- `npm run dev`, `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run build`
- `npm run api:sync`: re-export the OpenAPI schema from Django and regenerate
  `src/api/schema.d.ts`. Run it after any API change and commit both files; CI fails on drift.
- `npm run e2e`: Playwright (Chromium) against the real backend on :8001 and the production
  build (`vite build` into `dist-e2e`, `vite preview`) on :5174 (database `contribfinder_e2e`,
  re-seeded every run; one-time `npx playwright install chromium`). The auto fixture
  `policyViolations` (`e2e/fixtures.ts`) fails a test on any Content Security Policy console
  error in its context (canary `e2e/policy.spec.ts`); specs import `test` from `fixtures.ts`. `E2E_DEV_SERVER=1` runs the dev server (local
  only, no policy). Mutating specs each own a seeded user, one per attempt (`e2e_seed --attempts` from
  `RETRIES` in `playwright.config.ts`; the sessions file maps them to a list). New queries go through the shared client
  (`src/app/queryClient.ts`): 4xx are never retried, any 401 ends the session, and derived data
  is refetched by the data versions (`src/app/dataVersions.ts`, `AREA_KEYS`), not on mount: a
  new derived query under `['profile', ...]` must be listed in its area.

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
  schedules a Celery retry (never a hot loop), ETag conditional requests, Redis cache.
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

**Discovery and repository data** (MVP+, fix release)  ✅ shipped in v0.12.7 (no ranking change)

Archived: `openspec/changes/archive/2026-10-21-discovery-repository-data/`. Specs: deltas to
`repository-discovery`, `repository-analysis`. Batch 7 of `Bug_Backlog.md`.
- Rows are never deleted for a name: `lifecycle.release_name` renames the holder to
  `{full_name}~{github_id}` (`staleness.is_released_name`; its metadata counts as stale) and
  makes it ineligible `name_released` (INDEXED) until its analysis resolves it.
  Analysis fetches metadata by name and falls back to `get_repository_by_id` for a released
  name, a 404 or another ID. `hold(repo, fetched_name=...)` re-reads the locked row
  (`refresh_from_db(from_queryset=...)`, eligibility from current data) and raises `ClaimLost`
  when the name changed under a fetch without metadata.
- `upsert_repository(..., metadata_fetched=False)` for search results: `synced_at` only on
  create. Search stores each query's survivors in GitHub ID order (bulk repository locks are
  taken in GitHub ID order).
- `run(repo_id, parts)`: a FAILED retry fetches every part; otherwise stale parts ∩ `parts`,
  with metadata first for a released name. Nothing stale on a non-STALE row → release,
  SKIPPED (no transition stamp). Tests that force a part use
  `repo_fixtures.expire_parts`.
- Eligibility and RECOMMENDABLE/INDEXED change only in `services/repositories/lifecycle.py`.
  `recheck_eligibility(ids, now=)` (pool step) skips in-progress, FAILED, DISCOVERED and
  locked rows (`skip_locked`); STALE rows stay STALE.
- `not_code(..., has_dependencies=)`: no language → not code; a suspected list (`awesome-*`,
  excluded topic) is not code only once analyzed without manifest dependencies. Bulk callers
  annotate `has_dependencies_annotation()` and prefetch topics.
- Discovery steps: queries → search → interactions → pool → analysis. New metadata:
  `search_started_at` (older records are pruned at the pool step), `analysis_plan` (chosen
  once), `pool_eligibility_changed`, `pool_pruned_discoveries`. `pool_bands` may hold `other`.
  `PlannedQuery.core` has no star band. `ordering.pool_order(qs, *leading)` is the one
  candidate order (cap, analysis, API). The pool step writes inside `job_write`; pruning skips
  a run with no search and keeps records of `queries_skipped`.
- Backlog: `services/repositories/backlog.py` (`mark_stale`, `queue_batch`); its queued window
  is `job_guard.lost_before(now)`, shared with job recovery.
  `Repository.refresh_queued_at` holds a queued refresh back (abandoned claims excepted);
  `complete` and `fail` clear it. `lifecycle_changed_at` is non-null with a default.
- `DISCOVERY_STAR_BANDS` defaults to None: `queries.configured_star_bands()` derives the bands
  from `DISCOVERY_MIN_STARS` at call time (checks use it too); `core.W003` warns when the budget is
  not a multiple of the band count. Default `DISCOVERY_EXCLUDED_TOPICS` keeps generic topics
  (`list`, `books`): dependency evidence, not the topic list, keeps real code eligible.
- Review follow-ups X-1…X-6 of `Bug_Backlog.md` fixed in the same release; main specs updated
  directly (the archived deltas carry the same text).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Frontend correctness** (MVP+, fix release)  ✅ shipped in v0.12.8 (no ranking change)

Archived: `openspec/changes/archive/2026-10-21-frontend-correctness/`. Specs: new `web-client`;
deltas to `recommendations-view`, `recommendation-feedback`, `issue-matching`,
`developer-profile`. Batch 9 of `Bug_Backlog.md`.
- `createQueryClient({ navigate })` (`src/app/queryClient.ts`) is the one client for the app
  and tests: retries only network errors and 5xx (twice), default `staleTime` 5 min (status
  queries 0), and any 401 except `/auth/me` ends the session → `/?auth_error=session_ended`
  through `navigate`; `isActive` lives in `src/app/jobTransitions.ts`; the landing
  page clears the remaining cache on mount (clearing before the navigation commits lets the
  dashboard refetch it).
- `fetchStatusAndRefresh` (`src/app/jobTransitions.ts`) runs inside each status `queryFn` and
  refreshes derived data once per newly finished job (sync → `['profile']`; generation → list,
  details, issues, saved, and since 0.12.12 the developer profile, skills and interests;
  discovery → generation status). No per-observer effects.
- `positiveId` and `DeadEnd` for detail routes; `useScrollToHash(ready)` for hash links to
  content that loads later; saved/hidden lists are infinite queries (50 per page, by cursor
  since 0.12.12).
- Browser tests: `scripts/e2e-backend.mjs` runs `e2e_seed` (creates, migrates, seeds
  `contribfinder_e2e`) then Django; Playwright starts web servers before `globalSetup`, so the
  seed lives there. CI job `e2e`.
- Sign-out mutations carry `meta: { endsSession: true }` (`ENDS_SESSION_META_KEY`), which
  suspends the 401 handler; new sign-out flows must set it. `DJANGO_READ_DOTENV=0` stops
  `base.py` reading `.env`; `scripts/e2e-backend.mjs` sets it and passes only `DATABASE_URL`.
  It spawns Django with `detached: false` (0.12.12): Playwright stops a web server by `SIGKILL`
  to its process group, and a detached Django kept the pipe open, so CI hung after the last
  test. Every CI job has `timeout-minutes`.
- Review follow-ups Y-1…Y-5 and Y-8 of `Bug_Backlog.md` fixed in the same release; Y-6 (in
  part), Y-7 in 0.12.12; Y-9, Y-10 in batch 11.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Dev scripts, checks and migrations** (MVP+, fix release)  ✅ shipped in v0.12.9 (no ranking change)

Archived: `openspec/changes/archive/2026-10-21-dev-scripts-checks/`. Specs: new `developer-tooling`;
deltas to `api-platform`, `recommendation-engine`. Batch 10 of `Bug_Backlog.md`.
- Runners call `recordProcess()` (`child.mjs`), writing `.run/<script>-<pid>.json` with
  `{ pid, exe, marker }` (marker: the runner's script path) and removing it on exit;
  `stop.mjs` decides with the pure `matchStack(processes, records, repo, selfPid)`
  (`scripts/stack.mjs`): executable and marker must still match. A new runner only calls
  `recordProcess()`; a detached helper records itself with `{ pid, exe, marker }` (the WSL
  keep-alive: `wsl`, `sleep infinity`).
- Startup checks: scalar settings go through `_rule_errors(names, POSITIVE_INT |
  NON_NEGATIVE_INT | POSITIVE_NUMBER)`, mappings through `_keys_errors` (optional `item_ok`);
  the experience signal names are `services.profiling.experience.SIGNALS`.
- `runChild` tolerates an already-gone group and reports spawn errors; `waitPort` bounds each
  attempt by the remaining time; `scheduleFile(root)` (`env.mjs`) names beat's schedule.
- New check ids: `core.E050` (non-negative integer), `core.E051` (positive number); `core.E020`
  now also covers sync, job, GitHub, OAuth and repository integers; `core.E014` validates
  `EXPERIENCE_THRESHOLDS`. A new numeric setting needs a check in `sync_github_config_check` or
  its group.
- Seeds: `0002` activates v1 only when no other config is active; `0003` activates v2 only when
  nothing outside {v1, v2} is active. `tests/test_seed_migrations.py` round-trips them.
- `tests/test_privacy_coverage.py` fails for a new user-linked model until it is deleted by
  `delete_github_data` or kept on purpose, and its category is on `PrivacyPage.tsx`.
- `CELERY_TASK_IGNORE_RESULT = True`.
- A script that is also a CLI guards it with `isMain(import.meta.url)` (`env.mjs`, real paths),
  never `argv[1] === fileURLToPath(...)`. `scripts/uv.mjs` is a library, not a CLI.
- CI concurrency groups pushes by `github.sha` (a group keeps one pending run, so a shared group
  on `main` drops queued commits) and pull requests by ref with cancellation.
- Review follow-ups Z-2, Z-3, Z-6, Z-7 of `Bug_Backlog.md` fixed in the same release; Z-1 in
  0.12.12 (spec change), Z-4, Z-5, Z-8 and the `/simplify` skips Z-9, Z-10 in batch 11.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Performance and cleanup** (MVP+, fix release)  ✅ shipped in v0.12.10 (no ranking change)

Archived: `openspec/changes/archive/2026-10-22-performance-cleanup/`. Spec: delta to
`github-data-sync`. Batch 11 of `Bug_Backlog.md` (A-18 wontfix: a shared cache scope would let
the user's repository responses outlive "delete my data").
- GitHub client: ETag cache calls go through `_cached` (`services/github/client.py`); an error
  marks the cache down for `GITHUB_CACHE_BACKOFF_SECONDS` (default 30) via
  `core.backoff.Backoff`, which `core/throttling.py` uses too (one instance each, the caller's
  logger). `github:ratelimit:*` is no longer written; deletion still purges the user's key for
  one release (keys from before the upgrade). `Backoff.call(fn, *args, fallback=)` is the one
  try/skip wrapper; `conftest.py` runs `Backoff.reset_all()` and clears the health client.
- `job_guard.merge_metadata(job, **values)`: PostgreSQL `metadata || values` under the claim;
  discovery progress uses it. `repositories.queries.latest_snapshot(prefix)` (sliced
  `Prefetch`, `to_attr="latest_snapshots"`) is the one way to read a repository's newest
  snapshot. `lifecycle.complete(..., topics=, has_dependencies=)` takes what the analysis just
  stored. `core.health._redis_client(url)` is cached per process.
- Test fixtures shared by import live in `tests/shared_fixtures.py` (`make_developer`,
  autouse `single_band`, `developer`, `public_client` registered as `client`), not
  `conftest.py`: a global `client` would replace pytest-django's. Ruff ignores F811 in `tests/`.
  `tests/checks_helpers.ids`; frontend `callsTo` in `src/test/render.tsx`.
- `killTree(pidOrPids)` (one `taskkill` for many); `parsePs` (`scripts/stack.mjs`) names a
  process by its first argument. (CRLF checkouts failing `format:check` on Windows: fixed by
  `.gitattributes` in 0.12.11.)
- `merge_metadata(job, values, **fields)` is used by every job service that writes metadata
  (sync, discovery, generation); `save_progress` stays for steps only.
- Review follow-ups Q-1, Q-2, Q-4, Q-5, Q-7…Q-9 of `Bug_Backlog.md` fixed in the same release;
  Q-3, Q-6 accepted; Q-10…Q-12 (`/simplify` skips) and notes P-1…P-5 (batch 16) open.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Tooling and data hygiene** (MVP+, fix release)  ✅ shipped in v0.12.11 (no ranking change)

Archived: `openspec/changes/archive/2026-10-22-tooling-data-hygiene/`. Spec: delta to
`developer-tooling`. Batch 16 of `Bug_Backlog.md` (P-1…P-5) plus Q-10…Q-12.
- `scripts/redis.mjs` restarts a keep-alive that ends while the stack runs
  (`restartBudget`, `scripts/restarts.mjs`: 3 in 5 minutes); an intended stop sets `stopping`
  first. P-1's cause is still unknown; the log now shows the code in hex.
- `.gitattributes` `* text=auto eol=lf` (the index was already LF). `git checkout-index --force`
  does not rewrite clean-looking files; the README refresh deletes tracked files and checks
  them out again.
- Root `eslint.config.mjs` (scripts only) and `.prettierrc.json` (moved from `apps/frontend`;
  Prettier finds it upwards). CI's `api-contract` job runs root `npm ci`, `test:scripts`,
  `lint:scripts`, `format:scripts`.
- `api:export` runs through `scripts/manage.mjs`, so `npm run api:sync` needs no uv on PATH.
- `repositories.queries.SNAPSHOT_NEWEST_FIRST` is the one newest-snapshot order; the snapshot
  index is `(repository, -captured_at, -id)` (migration 0008). EXPLAIN: single-repository
  reads are index scan + limit; the `= ANY` prefetch still sorts (bitmap scan).
- `_update_metadata` wrappers removed (`merge_metadata(self.job, {...})`); tests import
  builders from `e2e.builders`.
- P-3 (flaky frontend tests) not reproduced in 8 runs under load; stays open.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Freshness, paging and seed** (MVP+, fix release)  ✅ shipped in v0.12.12 (no ranking change)

Archived: `openspec/changes/archive/2026-10-22-freshness-paging-seed/`. Specs: deltas to
`web-client`, `recommendation-feedback`, `recommendation-engine`. `Bug_Backlog.md` Y-6, Y-7, Z-1
(open outside a batch), plus the CI e2e hang fix.
- A finished generation also refreshes the developer profile, skills and interests (every
  analysis ends in one: analysis → discovery → generation). Since 0.12.15 the status keys live
  under `['jobs']`, so it invalidates all of `['profile']` (see 0.12.15 below).
- `/saved` and `/dismissed` use `feedback.api.KeysetPagination` (`SavedPagination`,
  `DismissedPagination`, `time_field`): `cursor` = unpadded URL-safe base64 of
  `"<iso time with µs>|<pk>"`, rows strictly older than it, `count` the total, `next` carries the
  cursor (never `page`), `previous` null (always, since 0.12.17); without one `page` works as
  before. An unreadable cursor is 400 `invalid_cursor` (`InvalidCursor`). `usePagedList` reads `cursor`
  from `next`. Not a contract break (OpenAPI `1.0.0`).
- `0003_seed_v2_deterministic.seed` returns early when v2 is stored: a re-apply after a rollback
  never changes activation. Re-activating v2 over v1 is not a benchmark improvement (P@5), so it
  takes `activate_scoring_config v2-deterministic --force --reason ...` (0.12.13).
  `test_v2_seed_replaces_v1` deletes v2 first (an upgrade has none).
- Y-6 leaves data with no generation after it (failed discovery) cached up to 5 min.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Config activation and loose ends** (MVP+, fix release)  ✅ shipped in v0.12.13 (no ranking change)

Archived: `openspec/changes/archive/2026-10-22-config-activation-loose-ends/`. Specs: deltas to
`recommendation-evaluation` (new "Activating a configuration"), `developer-tooling` (new
"Library scripts refuse to run as commands"). `Bug_Backlog.md` P-3, Q-10, `ideas.md` §15.
- `services/ranking/activation.activate(version, *, force, reason, via, user, request, judge)`:
  `stored_config` validation → already active is a no-op (no audit) → force needs a reason →
  `judge` (default `benchmark_judge`, looked up at call time so tests patch it; pinned
  `baseline.MIN_SCORE`/`TOP_N`, never settings) → one transaction locking every config row by
  pk, re-reading the active row (changed since judging → `ActivationError`) → audit. Forced, a
  comparison that cannot run (`ConfigError`, `DatasetError`) is recorded as `not compared: ...`
  instead of raised; `forced` is audited only when the rule was not met or not evaluated
  (0.12.14, S-1…S-4). Errors: `ActivationError`, `ActivationRefused(failures)`.
- Audit: `AuditEvent.Action.SCORING_CONFIG_ACTIVATED` (choices-only migration
  `accounts.0003`); allowed metadata `config_version`, `previous_version`, `forced`,
  `failures`, `via` (none identifying).
- P-3 cause: AppShell's lazy `LanguageChart` (Recharts) blocked the event loop ~1 s inside a
  random test on first import. `src/test/setup.ts` preloads it (since 0.12.15 through the
  `src/app/lazyLoaders.ts` registry).
- `refuseRun(import.meta.url)` (`env.mjs`) ends every library script (`child`, `env`, `stack`,
  `uv`, `restarts`): run directly they exit 1. A new library calls it too
  (`scripts/libraries.test.mjs` lists them).
- Q-10 accepted (bounded); the EXPLAIN is in `Bug_Backlog.md`.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Signal and explanation fixes** (MVP+, fix release)  ✅ shipped in v0.12.14 (no ranking change)

No OpenSpec change: the code now follows the existing specs (`skill-detection`,
`developer-profile`, `recommendation-explanations`). `Bug_Backlog.md` B-14, B-15, B-16, D-7 of
batch 8; the rest of batch 8 changes specified behavior and needs a change.
- README badge URLs are `html.unescape`d before parsing. A shields.io `/badge/` path is split on
  `-` before decoding (`--` literal); the label always counts, the message only with no label or
  a technology label (`_SECTION_TITLE`, `built/made/powered/written`), so free-text messages
  (`code style-black`) add no skill (S-5).
- `ContributionInput.observed_at` (`last_contributed_at`, else the repository's push) is the one
  date for contribution evidence; skill and interest collectors both read it.
- `explain.reasons` skips a signal whose contribution is 0 (weight 0).
- `feedback.api.KeysetPagination` applies its own order (`-time_field, -pk`); views do not order.
  Test helper `shared_fixtures.active_configs()`.
- Review of 0.12.13/0.12.14 (`Bug_Backlog.md` batch 18): S-1…S-5 fixed here, S-8 accepted; S-6
  (admin activation runs the benchmark in the request), S-7 (page-mode `previous` link) and the
  `/simplify` skips S-9…S-11 (`ideas.md` §17) open.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Fixes without a spec change** (MVP+, fix release)  ✅ shipped in v0.12.15 (no ranking change)

No OpenSpec change. `Bug_Backlog.md` D-12, D-13 (batch 8) and S-9…S-11 (batch 18).
- Issue difficulty measures the body without HTML comments (`classify._HTML_COMMENT`, template
  instructions, D-12); `labels._SCOPE` also strips a `[type]` prefix (D-13,
  `ISSUE_TAXONOMY_VERSION` 2026.10.3). Applied on the next issue fetch; baselines did not move.
- Job status query keys live under `['jobs']` (`recommendationStatusKey = ['jobs',
  'recommendations']`, `discoveryStatusKey = ['jobs', 'discovery']`); sync stays
  `['sync', 'status']`. A finished generation invalidates `['profile']`, a finished sync
  `['profile']` and `['jobs']`, restore also invalidates the generation status, delete-data
  removes `['jobs']`. A status key never goes under a prefix its own job invalidates.
- Lazy components only through `src/app/lazyLoaders.ts` (`lazy(lazyLoaders.X)`, never a bare
  `lazy()`); `src/test/setup.ts` awaits `preloadLazyComponents()`.
- Indexes `saved_keyset_idx (user, -saved_at, -id)`, `dismissed_keyset_idx (user,
  -dismissed_at, -id)` (`feedback.0003`).
- Open in batch 18: S-6 needs a decision (tracked job, or the admin points to the command); S-7
  needs an OpenSpec change (design D2 of `freshness-paging-seed` keeps the page `previous`).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Signal and explanation accuracy** (MVP+, fix release)  ✅ shipped in v0.12.16 (no ranking change)

Archived: `openspec/changes/archive/2026-10-24-signal-explanation-accuracy/`. Specs: deltas to
`recommendation-engine`, `recommendation-explanations`, `issue-matching`, `issue-analysis`.
`Bug_Backlog.md` D-8, D-9, D-15…D-18 of batch 8 (plus spec text for D-7, D-12, D-13); batch 8
keeps B-6 and D-11, which wait for K-1.
- Relevance gate: `score.has_relevance(signals, weights)` (value and weight above 0, never the
  rounded `Scored.relevance`); `score_candidate` stores it as `Scored.relevant`, `rank` reads
  it, and `rank_pool` passes the weights for the issue preselection (`is_relevant` removed in
  0.12.23).
- `issue_fit` evidence holds `technology_count`; `_issue_availability` picks technology / label
  only / mixed wording, and evidence without the key reads as all technology. An unknown-difficulty
  issue with a difficulty fit above 0 gets a `difficulty` reason with `estimated: False`.
- `ISSUE_DIFFICULTY` keys `several_technologies` and `min_votes` (defaults 2, `core.E040`);
  `classify.MIN_VOTES` is gone. `ISSUE_TAXONOMY_VERSION` stays 2026.10.3.
- `config.validate`: openness points sum to at most 1 (tolerance 1e-6).
- `ScoringConfig.save()` raises `ImmutableConfig` (a `ValidationError`) when a stored row's
  `FIXED_FIELDS` (version, weights, params) change; `update_fields` without them skip the check;
  `QuerySet.update` and migrations bypass it (activation and seeds touch `is_active` only). The
  admin shows the three read-only for every saved row. Tests needing other numbers create a
  new version.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Saved and hidden list links** (MVP+, fix release)  ✅ shipped in v0.12.17 (no ranking change)

Archived: `openspec/changes/archive/2026-10-24-keyset-paging-links/`. Spec: delta to
`recommendation-feedback`. `Bug_Backlog.md` S-7 (batch 18).
- `KeysetPagination` pages forward only: `previous` is always null, so every link it hands out
  is a cursor link. `cursor` together with `page` (any value) is 400 `cursor_with_page`
  (`CursorWithPage`), checked before the cursor is decoded; `page_size` works in both modes.
- `saved_list` and `dismissed_list` document `error_responses(400, 401)`. Not a contract break
  (OpenAPI `1.0.0`); the SPA never read `previous`.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Activation by command only** (MVP+, fix release)  ✅ shipped in v0.12.18 (no ranking change)

Archived: `openspec/changes/archive/2026-10-24-activation-command-only/`. Spec: delta to
`recommendation-evaluation`. `Bug_Backlog.md` S-6 (batch 18, option B).
- `ScoringConfigAdmin` has no `activate` action; its change page has a read-only `activation`
  field naming `npm run manage -- activate_scoring_config <version>` (or saying it is active).
  No benchmark comparison runs inside a web request.
- `activation.activate(version, *, force, reason, judge)`: `via`, `user` and `request` are gone;
  audit metadata `via` is always `"command"` (older admin entries keep `"admin"`).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Evaluation confidence** (MVP+)  ✅ shipped in v0.12.19 (no ranking change)

Archived: `openspec/changes/archive/2026-10-24-evaluation-confidence/`. Spec: delta to
`recommendation-evaluation` (new "Uncertainty of a comparison"). `ideas.md` §3 significance
testing.
- `services/evaluation/bootstrap.paired(baseline, candidate, *, resamples, seed) -> Interval`
  (`diff`, `low`, `high`, `not_better`, `marked`): paired over developers, percentile interval by
  nearest rank (rounded outwards), one `random.Random(seed)` per call. Defaults
  `DEFAULT_RESAMPLES = 10_000`, `DEFAULT_SEED = 20261024`.
- `DeveloperResult.values` holds the unrounded metrics; `runner.uncertainty(baseline,
  candidate, ...)` pairs by developer id. `compare`, activation and `baselines.json` never read
  the intervals.
- `evaluate_ranking` prints one block per candidate and dataset; `--resamples`, `--seed`; JSON
  `comparisons`. On `benchmark-v1`, v2 vs v1 NDCG@10 +0.0195 [-0.0023, +0.0501], not marked.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search); decide then whether
  the improvement rule also needs a marked NDCG@10.

**Feedback report** (MVP+)  ✅ shipped in v0.12.20 (no ranking change)

Archived: `openspec/changes/archive/2026-10-24-feedback-report/`. Spec: delta to
`recommendation-evaluation` (new "Feedback report"). `ideas.md` §4 online report per config.
- `services/evaluation/feedback_report`: `load(since, versions)` (one `values_list` query),
  `build(events, *, minimum, since_days)` (pure). Buckets `1-5, 6-10, 11-20, 21+`;
  `POSITIVE` = saved, opened_repository, opened_issue; `DECISIVE` adds dismissed. Group share
  `None` below `minimum` (default 10). Adjusted share: bucket shares weighted by every config's
  decisive actions per bucket, over the buckets where the config has a share.
- Events with a blank `config_version` or null `rank` are `unattributed`. User ids only count
  distinct users; the JSON holds no identifiers (test walks every key).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Feedback report: match labels** (MVP+)  ✅ shipped in v0.12.21 (no ranking change)

Archived: `openspec/changes/archive/2026-10-24-feedback-report-labels/`. Spec: delta to
`recommendation-evaluation` ("Feedback report"). `ideas.md` §4 label calibration.
- `Event.match_label` (default ""); `LabelRow` per `LABELS` (strong, good, partial), raw shares
  through the shared `_tally`; `calibration(rows) -> Calibration(verdict, higher, lower)`:
  `ordered` (ties included), `not ordered` with the first out-of-order pair, `not enough data`
  under two shares. Unlabeled attributed events stay in the bucket rows only.
- JSON per config: `labels`, `calibration`. Changing `params.bands` stays a ranking change.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Dismiss reasons** (MVP+)  ✅ shipped in v0.12.23 (no ranking change)

Archived: `openspec/changes/archive/2026-10-26-dismiss-reasons/`. Specs: deltas to
`recommendation-feedback`, `recommendation-evaluation` ("Feedback report"). `ideas.md` §4.
- `feedback.DismissReason` (`not_my_stack`, `too_big`, `inactive`, `already_know`);
  `DismissedRepository.reason` and `RecommendationFeedback.dismiss_reason`, blank when none
  (`feedback.0004`). `services.feedback.dismiss(user, recommendation, reason="")`; an already
  hidden repository keeps its stored reason.
- `DismissView` validates `DismissSerializer` (empty body = no reason); OpenAPI enum name
  `DismissReasonEnum` (`ENUM_NAME_OVERRIDES`). The hidden list's `reason` is null when blank.
- Frontend: `useDismiss().mutateAsync({ id, reason? })` sends a body only with a reason;
  `DismissReasonMenu` (`RecommendationActions.tsx`) is a home-made `role="menu"` (no new
  dependency): Escape returns focus to its button, a click elsewhere leaves focus there, and it
  stays closed while a dismiss is pending. Labels live in `features/feedback/messages.ts`.
  Playwright matches names by substring: locate the plain button with
  `{ name: 'Dismiss', exact: true }`.
- `feedback_report`: `Event.dismiss_reason`, `ConfigRows.dismiss_reasons` (most frequent first,
  `none` last), JSON `dismiss_reasons`; unattributed dismissals (no snapshot, or rank below 1)
  are counted by reason on their own line (`unattributed_dismiss_reasons`). Shares unchanged.
  `load` streams events unordered; buckets and labels share one accumulator (`_add`, `_rows`).
- Review fixes in the same release (`Bug_Backlog.md` batch 19, T-1…T-10):
  - Issue reasons come from one per-part `contrib` dict and need a contribution above 0; the
    unknown-difficulty text is "Difficulty not estimated". `MatchedIssue.mentions_technology`.
  - `ScoringConfig.save` compares the fixed fields as stored JSON.
  - `classify.LEVEL_VOTERS` lists which signals vote for each level: `MAX_LEVEL_VOTES` (4)
    bounds `min_votes` (`core.E040`); `core.W004` warns when a level is unreachable (3 or 4:
    intermediate has two voters). A test checks the table against the classifier.
  - Bootstrap: `bootstrap.draws(n, ...)` once per comparison, shared by its metrics
    (`paired(..., drawn=)`); `Interval.as_dict()`. `DeveloperResult.metrics` is a property of
    `values`. `KeysetPagination` builds one response in both modes. `config.SUM_TOLERANCE`.
  - Open from the review: T-11 (issue relevance ignores weights, waits for K-1), T-12 (rank 0
    storable; needs a constraint).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Setup readiness** (MVP+)  ✅ shipped in v0.12.24 (no ranking change)

Archived: `openspec/changes/archive/2026-10-26-setup-readiness/`. Specs: deltas to
`repository-analysis` ("Repository data collection"), `recommendations-view` (detail endpoint,
dashboard cards, detail page). `ideas.md` §8.
- `services/repositories/setup.py` (pure): marker tables, `detect(root, workflows) ->
  SetupFacts(ci, tests, dev_environment, docker_compose)`, `needs_workflows(root)` (a `.github`
  dir and no other CI marker). Names match lowercased, by entry type.
- The analysis' `dependencies` part lists the root once (`read_manifests(client, name, root)`),
  lists `.github/workflows` only when `needs_workflows` (`GitHubClient.list_contents`), and
  `_store` writes `Repository.has_ci`, `has_tests`, `has_dev_environment`,
  `has_docker_compose` (nullable; `repositories.0009`) with `dependencies_synced_at`.
- `SetupSerializer` as `setup` on list items and the detail. Frontend: `setupLine` and
  `SETUP_TEXT`/`SETUP_LABELS` (`features/recommendations/messages.ts`); cards list only facts
  found, the detail page reads Found / Not found / Not available (never "No").
- A test fails if any file under `services/matching`, `ranking`, `evaluation` or `discovery`
  reads a setup field: they are shown, never scored. Test fixture: `mock_repo_api(root=...,
  workflows=...)`.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Discovery yield report** (MVP+)  ✅ shipped in v0.12.25 (no ranking change)

Archived: `openspec/changes/archive/2026-10-27-discovery-search-yield/`. Spec: delta to
`repository-discovery` ("Candidate search", new "Discovery yield report"). `ideas.md` §12.
- `PlannedQuery.band` (label with more than one band, `""` with one; older stored plans load).
- `_step_search` writes `query_yield[key] = {source, band, results, rejections, recorded}` (or
  `{source, band, refused: true}` for a 422) in the same `merge_metadata` call as
  `queries_done` / `queries_skipped`. No query text; totals unchanged.
- `services/discovery/yield_report.py`: `load(since)` (finished discovery jobs, one query,
  unordered), `build(runs)` (pure; rows per strategy, band and both; `all` = single band),
  `as_dict()`. Command `repositories/management/commands/discovery_report.py` (the app's first
  management command).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search); acting on the
  report (§12) waits for it.

**Post-analysis pool cleanup** (MVP+)  ✅ shipped in v0.12.26 (no ranking change)

Archived: `openspec/changes/archive/2026-10-26-post-analysis-pool-cleanup/`. Spec: delta to
`repository-discovery` ("Candidate pool maintenance"). `ideas.md` §11; `Bug_Backlog.md` X-9.
- `_step_analysis` keeps `analysis_succeeded` (ids with outcome `analyzed`) and ends, inside
  `job_write`, with `_remove_not_code(pool, succeeded)`; records `analysis_not_code`.
- `_record_pool(extra)` records `pool_size` and `pool_bands` from the current pool: the pool
  step and the cleanup both call it, so the final metadata describes the pool the run leaves.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Data versions** (MVP+)  ✅ shipped in v0.12.27 (no ranking change)

Archived: `openspec/changes/archive/2026-10-27-data-versions/`. Specs: deltas to `sync-jobs`
(new "Data versions endpoint"), `web-client`. `ideas.md` §14; `Bug_Backlog.md` Y-6 (S-8
narrowed).
- `services/data_versions.versions(user)`: `github` = last completed sync, `profile` =
  `DeveloperProfile.analyzed_at`, `recommendations` = the latest of the last completed
  generation and the newest `staleness.PART_FIELDS` time of the user's recommended or saved
  repositories. Read-only, from stored times (no counter to bump). `GET /api/v1/sync/versions`
  (`DataVersionsView`, `sync_versions`); OpenAPI stays `1.0.0`.
- `src/app/dataVersions.ts` (fixed in 0.12.31, below): `dataVersionsKey = ['versions']`, `AREA_KEYS`, `changedAreas`,
  `useDataVersions` (pure `queryFn`; compares in an effect on `data` against the last value it
  saw, since 0.12.31; no previous value refetches nothing),
  `refreshDataVersions`. `SignedInLayout` observes it and refetches it on every route change;
  `staleTime: 0` covers focus. Status refreshes: sync → versions and `['jobs']`, discovery →
  versions and the generation status, generation → versions. Delete-data removes the key.
- Tests: `mockFetch` answers `/sync/versions` with the fixed `DATA_VERSIONS` unless a test
  passes its own; `changingVersions()` moves areas forward.
- No timer: a background refresh shows on the next focus, route change or finished job.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**New seeds stored inactive** (MVP+)  ✅ shipped in v0.12.28 (no ranking change)

Archived: `openspec/changes/archive/2026-10-27-new-seeds-inactive/`. Spec: delta to
`recommendation-engine` ("Versioned scoring configuration"). `ideas.md` §15.
- A seed after `v2-deterministic` calls `recommendations/migrations/_seeding.py`
  (`from . import _seeding`): `store_inactive(apps, *, version, description, weights, params)`
  forward (a stored version is left as it is), `remove_unused(apps, *, version)` in reverse
  (deletes only an inactive version without recommendations). The leading `_` keeps it out of
  the migration loader; it is frozen (new behavior = new function). Numbers stay frozen copies
  in the migration.
- `tests/test_seed_migrations.py` `ACTIVATING_SEEDS = {v1, v2}`; the migrated test database must
  have only `v2-deterministic` active and every stored configuration valid. Activation stays
  `activate_scoring_config` (README "Evaluating a ranking change" lists the steps).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Rank constraint** (MVP+, fix release)  ✅ shipped in v0.12.29 (no ranking change)

Archived: `openspec/changes/archive/2026-10-27-rank-constraint/`. Specs: deltas to
`recommendation-engine` (new "Stored ranks start at 1"), `recommendation-feedback` (new
"Feedback rank snapshot"). `Bug_Backlog.md` T-12.
- `CheckConstraint`s `recommendation_rank_positive`, `recommended_issue_rank_positive`
  (`rank >= 1`) and `feedback_rank_positive` (null or `>= 1`); migrations
  `recommendations.0005`, `issues.0002`, `feedback.0005` repair first (a developer's or
  recommendation's group with a rank 0 shifts up by one; an event's rank 0 becomes null),
  never delete. Generation writes through `bulk_create`, so only the database sees every writer.
- The repair is tested on the real upgrade path: migrate back before the three migrations,
  store rank 0 rows, migrate forward (`test_upgrade_repairs_rank_0_and_adds_the_constraints`).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Content Security Policy** (MVP+)  ✅ shipped in v0.12.30 (no ranking change)

Archived: `openspec/changes/archive/2026-10-27-content-security-policy/`. Specs: deltas to
`api-platform` (new "Content Security Policy"), `web-client` (new "Content Security Policy in
the built app"). `ideas.md` §5.
- `core.csp.ContentSecurityPolicyMiddleware` (after `SecurityMiddleware`) sets the header when
  absent: JSON media types (`is_json`) get `CONTENT_SECURITY_POLICY_API` (deny-all), anything
  else `CONTENT_SECURITY_POLICY_HTML` (same-origin, inline styles for the admin). Check
  `core.E060` refuses an empty or non-string policy.
- SPA: `apps/frontend/csp.config.ts` holds `CONTENT_SECURITY_POLICY` and the build-only plugin
  (`apply: 'build'`, meta tag `head-prepend`); `csp.config.test.ts` also checks `dist/index.html`
  when a build exists. A new script, image or API origin must be added there, or the built
  app breaks while the dev server (no policy) still works.
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Data versions fixes** (MVP+, fix release)  ✅ shipped in v0.12.31 (no ranking change)

Archived: `openspec/changes/archive/2026-10-27-data-versions-fixes/`. Specs: deltas to
`sync-jobs` ("Data versions endpoint"), `web-client` (both refresh requirements).
`Bug_Backlog.md` batch 20 (review of 0.12.24–0.12.30): U-1…U-3, U-5…U-7 fixed, U-4 accepted,
U-8 wontfix.
- `github` = the last *finished* sync (COMPLETED or FAILED; a failed sync may have stored
  data); `recommendations` still counts completed generations only.
- `AREA_KEYS.recommendations` includes `['profile', 'dismissed']`. A finished discovery refetches
  only the generation status. The versions `queryFn` is pure and the comparison runs in an
  effect on `data` (a cancelled or joined fetch cannot invalidate twice); call
  `useDataVersions` from one component only. Delete-data `resetQueries` the versions (never
  `removeQueries` an observed query). `versions()` is four reads since 0.12.44 (one `SyncJob` aggregate, plus the latest list change).
- `DiscoveryService._remove_not_code` returns the `RepositoryCandidate` count from
  `delete()`'s per-model counts (the total includes cascaded discovery records).
- Carry-over: K-1 unchanged (judge `real-a-v2` before any ranking search).

**Signal fixes** (MVP+, fix release)  ✅ shipped in v0.12.32 (no ranking change)

No OpenSpec change. `Bug_Backlog.md` B-6, D-11 (rest of batch 8), T-11 (batch 19); P-1 accepted.
- `experience.estimate_experience`: the level is the rounded mean with halves up, in integers
  (`2·total < n` beginner, `2·total < 3n` intermediate), as the docstring says (B-6).
- `classify.contribution_type`: the title keyword earliest in the title wins; `KEYWORD_TYPES`
  order only breaks a tie (D-11). `ISSUE_TAXONOMY_VERSION` 2026.10.4.
- `MatchedIssue.relevant` and `mentions_technology` come from the per-part contributions, as
  the reasons do (T-11); `issue-matching` spec "Issue relevance" edited directly.
- Benchmarks store experience levels and issue types/difficulties, so none of these move the
  baselines; stored profiles and issues change on their next analysis or fetch.
- Open items: none. Known gaps K-1…K-5 remain.

**JSON report writer** (MVP+, cleanup)  ✅ shipped in v0.12.33 (no ranking change)

Archived: `openspec/changes/archive/2026-10-28-json-report-writer/` (no spec change,
`skip_specs`). `Bug_Backlog.md` T-14, `ideas.md` §15.
- `core/reports.py`: `json_text(data)` (indent 2, `ensure_ascii=False`, trailing newline) and
  `write_json(out, data, *, what)` (creates folders, UTF-8, `OSError` →
  `CommandError("<what> not written to <out>: ...")`). Every management command that writes
  JSON uses it (`evaluate_ranking`, `feedback_report`, `discovery_report`,
  `export_benchmark_developer`, `import_judgments`, `build_benchmark`, `e2e_seed`); a new one
  must too. Not used for `benchmark_sheet` (CSV) or `baselines.json` (`services/evaluation/baseline.py`).

**Dependency audit** (MVP+, platform)  ✅ shipped in v0.12.34 (no ranking change)

Archived: `openspec/changes/archive/2026-10-28-dependency-scanning/`. Spec: delta to
`developer-tooling` (new "Dependencies are audited for known vulnerabilities"). `ideas.md` §5.
- `scripts/audit.mjs` (pure parts tested in `audit.test.mjs`): `pythonFindings`, `npmFindings`,
  `validateAccepted`, `unusedAccepted`, `failing`. pip-audit repeats an advisory once per fixed
  version; findings are keyed by advisory id. npm severities below high are reported only.
  Environment markers are stripped from the export (`withoutMarkers`: pip-audit drops a
  requirement whose marker is false on the host, so Linux CI skipped Windows-only packages); a
  package pip-audit skips fails.
- Workflow `audit.yml` installs nothing; its concurrency group includes the event, so the
  weekly run never replaces a push run.
- First audit: certifi, djangorestframework 3.18.3, shell-quote (via concurrently), vite 8.3.5,
  zod 4.6.7, undici 8.12.3, source-map-js 1.2.2 upgraded; nothing accepted.
- Review of 0.12.32–0.12.34 (`Bug_Backlog.md` batch 21): M-1…M-3, M-9…M-11 fixed here; the
  rest accepted or wontfix. A malformed report goes through `asAuditError` (exit 2, no stack).

**Labeled-issue fetch** (MVP+, ranking-visible through data)  ✅ shipped in v0.12.35

Archived: `openspec/changes/archive/2026-10-28-labeled-issue-fetch/`. Spec: delta to
`issue-ingestion` ("Issue collection"). `ideas.md` §7.
- `list_open_issues(full_name, *, label=None)`: with a label, `labels=<label>` and one page
  (`labels=a,b` would require both). The `issues` part reads the recent listing, then one
  labeled listing per `ISSUES_ENTRY_LABELS` entry (default `good first issue`, `help wanted`;
  check `core.E041`) **only when the recent listing is truncated** (an untruncated one holds
  every open issue; 410 reads as empty). `merge_issue_pages` (analysis.py): recent first, then
  unseen by GitHub ID; `issues_truncated` describes the recent listing only. Any listing
  failing fails the part and keeps the stored issues.
- No scoring or config change; the benchmark stores issues, so baselines cannot move (design
  D6). Local measurement (read-only): 50 of 473 pooled repositories capped; 84 entry issues
  stored before; 24 repositories gain 550 more (390 updated within `ISSUE_MAX_AGE_DAYS`).
- Tests register labeled `respx` routes before the generic issues route (first match wins).
- Review (`Bug_Backlog.md` batch 22): names trimmed in `base.py` (`env.list` keeps spaces after
  commas); `_between_parts` before each labeled listing; N-4…N-7 accepted.
- Comma-separated settings go through `env_list(name, default)` in `base.py` (trimmed, empty
  items dropped), never bare `env.list` (N-8).

**Released-name refresh** (MVP+)  ✅ shipped in v0.12.36 (no ranking change)

Archived: `openspec/changes/archive/2026-10-29-released-name-refresh/`. Spec: delta to
`repository-analysis` ("Background refresh"; edited directly after the review). `ideas.md` §13.
- `lifecycle.release_name` returns the holder pks; `storage.upsert_repository` passes them to
  `backlog.queue_released(pks, timezone.now())`: pooled rows not IN_PROGRESS/FAILED/queued are
  stamped `refresh_queued_at` in the caller's transaction, and `sync_repository.delay` is sent
  `on_commit`. Nothing without app credentials or under `CELERY_TASK_ALWAYS_EAGER`.
- `lifecycle.NameChanged(ClaimLost)`: `hold(fetched_name=...)` raises it; the analysis releases
  and calls `queue_released([pk], ..., requeue=True)` (its own stamp no longer counts) (L-1).
- `backlog.AUTH_INVALID` (`github_auth_invalid`) within `REPO_REFRESH_RETRY_MINUTES` holds the
  immediate refresh back; other refresh failures do not (L-2). `_pick`, `_not_queued`,
  `_refresh_failed` are shared with `queue_batch` (L-4). Review: `Bug_Backlog.md` batch 23.

**Route-level id validation** (MVP+, refactor)  ✅ shipped in v0.12.37 (no ranking change)

Archived: `openspec/changes/archive/2026-10-30-route-id-validation/` (no spec change,
`skip_specs`). `ideas.md` §14.
- `RouteId({ invalid, children: (id) => ReactNode })` (`src/routes/RouteId.tsx`) is the one
  place a detail route's `:id` is validated (`positiveId`, private to it since `/simplify`): invalid → `DeadEnd` with `invalid`,
  no request; valid → `children(id)` in a `Fragment` keyed by the id (remount per id: scroll-to-hash and
  page state reset; `RouteId.test.tsx` guards it). A new
  detail route wraps its page the same way in `routes.tsx`.
- Detail pages take `{ id: number }`; `useRecommendation`/`useIssue` trust their argument (no
  `enabled` guard). Review: `Bug_Backlog.md` batch 24 (RT-3…RT-5 open).

**Browser tests on the production build** (MVP+, platform)  ✅ shipped in v0.12.38 (no ranking change)

Archived: `openspec/changes/archive/2026-10-30-e2e-production-build/`. Spec: delta to
`web-client` ("End-to-end coverage of the main flows"). `ideas.md` §14.
- `playwright.config.ts`: the frontend server runs `vite build --outDir dist-e2e --emptyOutDir`
  then `vite preview --outDir dist-e2e --port 5174 --strictPort` (timeout 180 s);
  `E2E_DEV_SERVER=1` runs the dev server (local only, no policy). `dist-e2e` is in
  `.gitignore`, the ESLint ignores and `.prettierignore`.
- `vite.config.ts`: one `proxy` constant for `server.proxy` and `preview.proxy`.
- `e2e/fixtures.ts`: auto fixture `policyViolations` collects, on `context.on('console')`,
  errors containing `Content Security Policy`, yields `{ seen, take() }` and fails the test with
  any not taken;
  every spec imports `test` from `fixtures.ts`. Canary `e2e/policy.spec.ts` (skipped under
  `E2E_DEV_SERVER=1`) blocks a foreign image and `take()`s the violation (expected `img-src` from
  `CONTENT_SECURITY_POLICY`). The preview runs with `--host localhost` (e2e command, not
  `vite.config.ts`); the frontend server pipes stdout. Review: batch 25. A new script, image or API origin missing from `csp.config.ts` now fails CI.
- Task 3.3 closed: CI (e2e included) green on `main` after the push. No carry-overs.

**Settings fixes, review sweep: config** (MVP+, fix release)  ✅ shipped in v0.12.39 (no ranking change)

Archived: `openspec/changes/archive/2026-10-30-config-review-fixes/` (no spec change,
`skip_specs`). `Bug_Backlog.md` batch 26 (CFG-1…CFG-20), the first module of the full review
sweep (workflow in `Bug_Backlog.md`). Also `LICENSE` (MIT), `SECURITY.md`, SRS files untracked.
- `DJANGO_READ_DOTENV`: unset/true reads `.env`, `0` skips it (e2e), `DATABASE_URL` (the test
  settings) takes only that key, via `_dotenv_value(path, key)` (django-environ's parser into a
  local mapping, never `os.environ`). Local pytest thus matches CI except `REDIS_URL`, which CI
  sets.
- Settings helpers in `base.py`: `env_list` (commas), `env_words` (spaces or commas),
  `env_json(name, default)` (blank = default, invalid → `ImproperlyConfigured` naming it),
  `env_mapping(name, defaults)` (JSON object merged over defaults). New JSON settings use them,
  never bare `env.json`.
- `CELERY_BROKER_TRANSPORT_OPTIONS` (one dict after `GITHUB_MAX_RETRY_DELAY`):
  `socket_timeout` ≥ 2 s, `visibility_timeout = max(3600, 2 * GITHUB_MAX_RETRY_DELAY)`.
  `CONN_HEALTH_CHECKS = True`. `LOG_LEVEL` sets root and `django`; `django.db.backends` stays at
  INFO (no SQL parameters in logs).
- `config/exceptions.py`: dict detail → default message plus `details`; list detail → message.
- CFG-7 (500s bypass `got_request_exception`) and CFG-8 (production re-reads `REDIS_URL`)
  accepted.

**Core fixes, review sweep: core** (MVP+, fix release)  ✅ shipped in v0.12.40 (no ranking change)

Archived: `openspec/changes/archive/2026-10-30-core-review-fixes/`. Spec: delta to
`api-platform` ("Configuration validated at startup"). `Bug_Backlog.md` batch 27 (CORE-1…CORE-10),
the second sweep module. `/simplify` and the fix-diff `/code-review` were skipped (owner).
- `core.startup.run_startup_checks`: `checks.run_checks(include_deployment_checks=True)`;
  silenced messages dropped first, serious ones block, the rest are logged.
- `core/checks.py`: `NUM_PROXIES` in `NON_NEGATIVE_INT_SETTINGS`; query shares need a positive
  total (`core.E022`); CSP values without control characters (`core.E060`); `REPO_STALE_AFTER`
  items positive (`core.E023`); `_between(value, low, high)` for ranged numbers, so a wrong type
  is an error, never a `TypeError`. Strategy and part keys come from `queries.STRATEGIES` and
  `staleness.PARTS`, imported inside the check (they import models).
- `core/logging.py`: keys match at the end of a longer name (`_NAME`); keys include `secret`,
  `password`, `sessionid`, `csrftoken`, `encryption_keys`; `key=value` stops at `;` (cookies).
- `core.reports.write_json`: serialize first, temporary file in the target folder, `os.replace`.

**Account fixes, review sweep: accounts** (MVP+, fix release)  ✅ shipped in v0.12.41 (no ranking change)

Archived: `openspec/changes/archive/2026-10-30-accounts-review-fixes/`. Specs: deltas to
`github-authentication` ("Handle the authorization callback", "Disconnect GitHub", "Audit trail
for sensitive account actions"), `data-controls` ("Delete account"). `Bug_Backlog.md` batch 28
(ACC-1…ACC-20; ACC-4 accepted, ACC-17 in part). ACC-11…ACC-20 came from a `/code-review` that
narrowed to the uncommitted diff and were fixed before commit.
- `services/accounts.py`: `disconnect_github(user, request) -> "queued" | "not_connected"` and
  `delete_account(user, request)`, each one `@transaction.atomic` around the shared `_leave` (data deletion, audit,
  anonymization and `user.delete()` all or nothing); views add only `logout`.
- `services.github.accounts`: `queue_revocation(encrypted, github_id, *, grant)` (the one way to
  revoke: `transaction.on_commit(..., robust=True)`, so a broker error is logged, never raised)
  and `revoke(encrypted, github_id, *, grant)`: a token still stored for `github_id` is never
  revoked, and once the user signed in again only the old token goes (never the grant); a token
  under a removed key is logged and skipped. Disconnect/deletion queue `grant=True` with the
  GitHub ID, a replaced token `grant=False`, a refused sign-in `refuse_token` (`grant=True`, no ID).
- Task `github.revoke_later(encrypted, github_id, grant)`: retries through
  `services/github/retry.decide_retry` (`REVOCATION_ATTEMPTS = 4`; `oauth._revoke` raises
  `GitHubTransientError` for network, 5xx and 429, `OAuthError` otherwise); a final failure
  records `AuditEvent.Action.GITHUB_REVOCATION_FAILED` (reason only, no user, `accounts.0005`).
  `github.revoke_replaced_token` only forwards messages queued before 0.12.41.
  Nothing on the request path calls GitHub (invariant 3).
- `link_github_account` raises `AccountInactive` for a deactivated user before writing anything;
  the callback maps it to `refuse_token`, audit `account_inactive`, `failed`; any other exception
  while linking or logging in → audit `internal_error`, `failed`. No
  `throttle_scope` on the callback.
- `AuditEventAdmin`: no add/delete, `list_select_related`; index `auditevent_created_idx`
  (`accounts.0004`). Beat `clear-expired-sessions` (daily) → `accounts.clear_expired_sessions`.
- Disconnect response `revocation`: `queued` | `not_connected` (`revoked`, `failed` kept in the
  enum, unused; OpenAPI `1.0.0`).

**GitHub app fixes, review sweep: github** (MVP+, fix release)  ✅ shipped in v0.12.42 (no ranking change)

Archived: `openspec/changes/archive/2026-10-31-github-review-fixes/`. Specs: deltas to
`data-controls` ("Delete GitHub-derived data"), `sync-jobs` ("Synced data endpoints").
`Bug_Backlog.md` batch 29 (GH-1…GH-15; GH-6, GH-9, GH-12, GH-14, GH-15 accepted, GH-11 wontfix).
- `services/accounts.delete_github_data(user, request)`: `@transaction.atomic` around
  `data_deletion.delete_github_data` and the `github_data_deleted` entry; the view only calls it.
  Same name as the routine: import the module (`accounts.delete_...`), never the bare name.
- `core/admin.NoAddDeleteAdmin[M]` (no add, no delete) for `AuditEventAdmin`, `GitHubAccountAdmin`,
  `GitHubProfileAdmin`. The admin thus cannot delete a User with GitHub data (cascade);
  `delete_account` is the path (GH-9).
- `services/github/retry.attempt_number(executed, max_attempts, *, eager)` is the one "eager =
  last attempt" rule (`run_tracked_job`, `revoke_later`). `revoke_later` logs a traceback for
  `internal_error` except `OAuthError` (GitHub refusing).
- `RepositoryPagination.max_page_size` is a property: `max(100, GITHUB_SYNC_MAX_REPOS)`.
  `useRepositories` keeps `page_size=100` and fetches each `next` by its own query (with the
  query's `signal`) into one page with the first `count`. `RepositoryListView` has no `distinct`.

**Seed fixes, review sweep: e2e** (MVP+, fix release)  ✅ shipped in v0.12.43 (no ranking change)

Archived: `openspec/changes/archive/2026-10-31-e2e-seed-review-fixes/`. Spec: delta to
`web-client` ("End-to-end coverage of the main flows"). `Bug_Backlog.md` batch 30 (SEED-1…SEED-19;
SEED-13, SEED-14, SEED-18 accepted). `/security-review` of `e2e/`: nothing.
- `e2e_seed`: `refuse_unless_e2e(installed_apps, database)` (app and `E2E_DATABASE`
  `contribfinder_e2e`) before any side effect; `seed(attempts) -> {user: id | [id per attempt]}`
  (`READ_USERS`, `UNSYNCED_USER` one id; `MUTATING_USERS` `e2e-save`, `e2e-dismiss`,
  `e2e-delete`, copies `<user>-retry<n>`, never `~`: `staleness.RELEASED_MARK`). `_reset` also
  clears sessions and audit entries.
- `playwright.config.ts` `RETRIES` → `scripts/e2e-backend.mjs <sessions> <attempts>` →
  `--attempts`. `fixtures.ts` `signInAs` reads the sessions file once: a string serves every
  attempt, a list is indexed by `testInfo.retry` (missing → error naming the attempt). A new
  data-changing spec adds its user to `MUTATING_USERS` and `SeededUser`.
- `services.jobs.new_job(user, job_type)` builds a PENDING job (no checks; `_start_job` uses
  it). `e2e.builders.make_issue -> Issue`; `add_candidate` keeps the candidate's times within its
  records'.

**Service fixes, review sweep: services** (MVP+, fix release)  ✅ shipped in v0.12.44 (no ranking change)

Archived: `openspec/changes/archive/2026-10-31-services-review-fixes/`. Specs: deltas to
`recommendation-engine` ("Recommendation generation job"), `sync-jobs` ("Data versions
endpoint"). `Bug_Backlog.md` batch 31 (SVC-1…SVC-20; SVC-16 open, accepted rows listed there).
`/security-review` of `services/*.py`: nothing.
- `data_deletion.delete_github_data` captures `user_id` first (account deletion deletes the user
  before commit); purges on commit and queues `github.purge_user_cache(user_id)` with
  `countdown=SYNC_STALE_AFTER_SECONDS` (robust). Root fix still open: SVC-16 (per-user ETag
  cache generation).
- `_delete_orphans` locks the touched repositories in GitHub ID order (every bulk repository lock
  uses it), then deletes and counts from `delete()`.
- `run_tracked_job(..., on_failed=)` runs after a final failure (never a retry or cancel), through
  `_follow_up` like `on_completed`; generation passes `rerun_recommendations_if_requested` to
  both. `_end_jobs` locks `order_by("pk")`; `claim_job` returns None for a job gone after the claim.
- `services/feedback._current(recommendation, lock=)` re-reads what an event snapshots;
  `opened_issue` locks its issue after the recommendation (gone → no event).
- `data_versions`: `recommendations` also takes the latest `feedback.LIST_ACTIONS` event
  (saved, unsaved, dismissed, undismissed); partial index `feedback_list_change_idx`
  (`feedback.0006`). Four reads.

**GitHub service fixes, review sweep: services/github** (MVP+, fix release)  ✅ shipped in v0.12.45 (no ranking change)

Archived: `openspec/changes/archive/2026-11-02-github-services-review-fixes/`. Spec: delta to
`github-data-sync` ("Credential use during sync", "External contribution ingestion").
`Bug_Backlog.md` batch 32 (GHS-1…GHS-10). Fix-diff review of 0.12.45–0.12.47: one `/simplify`
and one `/code-review` over the combined diff, batch 35 (FD-1…FD-10), archived as
`2026-11-02-fix-diff-review-fixes` (delta to `github-authentication` "Disconnect GitHub").
- The repositories step chooses by push time and upserts in GitHub ID order (the bulk lock
  order). Callers of `storage.replace_languages`/`replace_dependencies` hold the repository
  row lock: the sync's languages and dependencies steps call `storage.lock_repository(repo)`
  inside `job_write`; `upsert_repository` and the analysis' claim already hold it.
- `client._api_origin(url)` (scheme, host, port of `GITHUB_API_BASE_URL`) is the one origin check
  (redirects, `_link(header, rel)` for `next` and `last`). `_send` maps `httpx.InvalidURL` to
  `GitHubClientError` and any other `httpx.HTTPError` to `GitHubTransientError`; httpx raises
  `RemoteProtocolError` (transient) for a malformed Location itself.
- `services/github/errors.py` holds `API_VERSION`, the secondary-limit constants and
  `error_for_response(response, path)` (the one status → error mapping). `oauth._revoke` passes a
  403/429 to it and raises a `GitHubRateLimited` (retried by `revoke_later`); `client` and
  `oauth` both import from `errors`, never from each other's privates. `revoke_later` retries a
  rate limit after `min(wait, GITHUB_MAX_RETRY_DELAY)` (FD-1); the shared policy would fail it.
  Test helper `test_github_sync.running_sync_job(user)` builds a RUNNING sync job.
- `GITHUB_ETAG_MAX_BYTES` (256 KiB, `core.E020`): larger 200 bodies are not cached.
- Contributions: `_merge_by_repository` sums plan items per stored pk; `_store_contributed_repository`
  returns None for 404 or now-owned and lets other `SKIPPABLE` errors through, recorded in
  `contrib_skipped` (links kept by `full_name__iexact`). Dependencies: `dependencies_ids` frozen
  on the first attempt. `client.parse_dt` is the one GitHub time parser (`sync` uses it).

**API client fixes, review sweep: frontend/src/api** (MVP+, fix release)  ✅ shipped in v0.12.46 (no ranking change)

Archived: `openspec/changes/archive/2026-11-02-api-client-review-fixes/`. Spec: delta to
`web-client` ("Retry policy", new "Request failures"). `Bug_Backlog.md` batch 33 (API-1…API-5,
API-9 fixed; API-6, API-7 accepted; API-8 false positive). Fix-diff review: batch 35 (see
0.12.45).
- `apiFetch` throws only `ApiError`: `send()` wraps a fetch rejection as `ApiError(0,
  'network_error')` (an `AbortError` passes through for TanStack Query), a 2xx body that is not
  JSON is `ApiError(status, 'invalid_response')`; the non-envelope error keeps `retryAfter`.
- `isRetryable` (`src/app/queryClient.ts`): only `ApiError` with status 0 or 5xx.
- `ensureCsrfToken({ keepalive })` shares one module-level `pendingCsrf`; a non-ok `/auth/csrf/`
  raises `toApiError`; `csrf_unavailable` only when an ok answer set no cookie. `apiFetch`
  forwards `init.keepalive`.
- `ApiInit` = `RequestInit` with `json` (exclusive with `body`): sets `Content-Type` and
  `JSON.stringify`. New JSON callers use it, never a hand-built header.

**Sign-in and sign-out fixes, review sweep: frontend/src/features/auth** (MVP+, fix release)  ✅ shipped in v0.12.47 (no ranking change)

Archived: `openspec/changes/archive/2026-11-02-auth-review-fixes/`. Spec: delta to `web-client`
("Ended session returns to sign-in", new "Leaving the signed-in app"). `Bug_Backlog.md` batch 34
(AUTH-1…AUTH-9). Fix-diff review: batch 35 (see 0.12.45).
- `authErrorMessage` reads own keys only (`Object.hasOwn`).
- `RequireAuth` renders the `Outlet` whenever `me.data` exists. The query cache runs
  `endSession` on a 401 from `/auth/me` only when that query held data (a first visit stays
  silent).
- `src/app/session.ts` holds the session primitives: `meQueryKey`, `ENDS_SESSION_META_KEY`,
  `Navigate`, `isMe`, `endSession` and `leaveSignedIn` (one `leave` core: cancel, remove the
  identity, navigate; `leaveSignedIn` then `clearSignedInData`). `queryClient.ts` and
  `features/auth/api.ts` (which re-exports `meQueryKey`, `ENDS_SESSION_META_KEY`) import it, never
  each other. Log out, disconnect and delete account
  (`useSignOutMutation`) call it from the hook's `onSuccess`; components call `mutate()` with no
  callbacks. Delete GitHub data cancels `['profile']`/`['jobs']`, awaits the identity and
  `['sync']` refetch, navigates to `/onboarding` from the hook, then removes them.
- `accountMutationKey = ['account']` prefixes the four account mutations;
  `useAccountActionPending()` disables every account button (sections and Log out). A new
  account action uses the key.

**Job fixes, review sweep: jobs** (MVP+, fix release)  ✅ shipped in v0.12.48 (no ranking change)

Archived: `openspec/changes/archive/2026-11-02-jobs-review-fixes/`. Specs: deltas to `sync-jobs`
(new "Stalled jobs are reported"), `web-client` (new "Stalled job"). `Bug_Backlog.md` batch 36
(JOB-1…JOB-10; JOB-9, JOB-10 accepted, JOB-8 partial). One `/simplify` over the combined 0.12.48–0.12.50 diff (batch 39); the fix-diff
`/code-review` was skipped (owner).
`/security-review` of `jobs/`: nothing.
- `job_guard.is_stalled(job, now)`: RUNNING with `updated_at < stale_before(now)`;
  `services.jobs._stale_running` is its query form (a test checks they agree). `SyncJobSerializer`
  exposes it as `stalled` on every returned job (sync, discovery, generation status, start).
  Reading never changes the job.
- SPA: `isStalled(job)` (`src/app/jobTransitions.ts`) is active and stalled. `isActive` stays
  true for a stalled job (polling continues, no finished-job refresh); `usePipelineStage`
  returns `'stalled'` when the first active job of the chain is stalled; AppShell's Refresh and
  onboarding's Try again work over a stalled sync (the start fails it `worker_lost`). Test job
  fixtures carry `stalled: false`.
- `jobs.models.JobStatus` (module level; `SyncJob.Status` is the same class) and
  `ACTIVE_STATUSES`: the one active list, also for the unique constraint and the partial index
  `syncjob_active_updated_idx` (`jobs.0007`). `SyncJob.is_active` removed.
- `SyncJobAdmin(core.admin.ViewOnlyAdmin)` (view only: a save would overwrite a worker's claim
  and bump the heartbeat); `list_select_related`. Beat `recover-stale-jobs` has
  `options.expires = JOB_RECOVERY_INTERVAL_SECONDS`.

**Developer profile fixes, review sweep: developers** (MVP+, fix release)  ✅ shipped in v0.12.49 (no ranking change)

Archived: `openspec/changes/archive/2026-11-02-developers-review-fixes/` (no spec change,
`skip_specs`). `Bug_Backlog.md` batch 37 (DEV-1…DEV-9; DEV-6 accepted with a guard test).
One `/simplify` over the combined 0.12.48–0.12.50 diff (batch 39); the fix-diff
`/code-review` was skipped (owner). `/security-review` of
`developers/`: nothing.
- The developer admins use `core.admin.ViewOnlyAdmin` (no add, change or delete): developer
  data and catalog rows are removed only by `data_deletion`. `list_select_related` per admin;
  `InterestEvidenceInline`.
- `developers.models.EVIDENCE_ORDER` (source, `observed_at` desc nulls last, pk): model ordering
  and both API prefetches. Skill and interest lists end with `pk` (`developers.0002`, state only).
- `reanalyze_profiles`: active users only; a user with an active sync (`active_jobs`, so not a
  stalled one) is skipped and counted `syncing`.
- `tests/test_developers_review_fixes.py` fails once `SKILLS` or `INTERESTS` exceeds
  `ProfileListPagination.max_page_size` (200): the SPA (`features/profile/api.ts`) reads one page.

**Repository data fixes, review sweep: repositories** (MVP+, fix release)  ✅ shipped in v0.12.50 (no ranking change)

Archived: `openspec/changes/archive/2026-11-02-repositories-review-fixes/`. Spec: delta to
`repository-analysis` ("Background refresh"). `Bug_Backlog.md` batch 38 (REPO-1…REPO-8; REPO-8
accepted). One `/simplify` over the combined 0.12.48–0.12.50 diff (batch 39); the fix-diff
`/code-review` was skipped (owner). `/security-review`
of `repositories/`: nothing.
- Every repository admin uses `core.admin.ViewOnlyAdmin` (`NoAddDeleteAdmin` plus no change);
  inlines `can_delete = False`, `list_select_related` per list.
- `_refresh` (`repositories/tasks.py`) decides through `attempt_number(..., eager=)`;
  `internal_error` is logged with `logger.exception`. Database errors are still not retried
  (shared policy); the refresh failure delay retries them.
- `backlog.mark_queued(pks, now)` (a scheduled retry renews `refresh_queued_at`) and
  `backlog.unmark_queued(pks)` (a send the broker refused); `process_repository_backlog` tries
  every send and returns the number sent.
- Viewing a repository in the admin raises Django's `RemovedInDjango60Warning` (URLField scheme);
  `FORMS_URLFIELD_ASSUME_HTTPS` is not set yet.
- `/simplify` (batch 39): `core.admin.ViewOnlyAdmin` (`NoAddDeleteAdmin` plus no change) is the
  one view-only base; a new admin for job-written data uses it. `recommendations/admin.py`'s own
  `ReadOnlyAdmin` (allowed delete, SIM-8) was removed in 0.12.52. Admin tests use `shared_fixtures.assert_view_only(model, user, obj)` and
  `changelist_queries(client, url)` with pytest-django's `admin_user`/`admin_client`. SPA:
  `features/sync/messages.STALLED_NOTICE`; `isStalled` reads `job.stalled` only.

**Issue data fixes, review sweep: issues** (MVP+, fix release)  ✅ shipped in v0.12.51 (no ranking change)

Archived: `openspec/changes/archive/2026-11-03-issues-review-fixes/` (no spec change,
`skip_specs`). `Bug_Backlog.md` batch 40 (ISS-1…ISS-8; ISS-3, ISS-4, ISS-6 accepted).
`/simplify` and the fix-diff `/code-review` were skipped (owner). `/security-review` of
`issues/`: nothing.
- `IssueAdmin` and `RecommendedIssueAdmin` use `core.admin.ViewOnlyAdmin` (deleting an issue
  cascaded into recommended issues and left the recommendation's issue snapshots stale);
  `IssueAdmin.list_select_related = ("repository",)`. SIM-8 closed in 0.12.52.
- `IssueTechnologySerializer.source` choices are `technologies.TITLE`, `LABEL`, `BODY`.
- Detail staleness (current skills for "matched", an issue assigned, locked or transferred
  since generation) is bounded by the freshness sweep; design D3 rejects a detail-only filter
  (the recommendation would still link an issue that 404s).

**Recommendation fixes, review sweep: recommendations** (MVP+, fix release)  ✅ shipped in v0.12.52 (no ranking change)

Archived: `openspec/changes/archive/2026-11-03-recommendations-review-fixes/` (no spec change,
`skip_specs`). `Bug_Backlog.md` batch 41 (REC-1…REC-10; REC-5 false positive) and SIM-8.
`/simplify` and the fix-diff `/code-review` were skipped (owner). `/security-review` of
`recommendations/`: nothing.
- `recommendations.admin.ReadOnlyAdmin` is gone: `RecommendationAdmin` and the feedback admins
  use `core.admin.ViewOnlyAdmin` (reason inline `can_delete = False`, `list_select_related`
  each). `ScoringConfigAdmin` is `NoAddDeleteAdmin`: configurations come from seed migrations;
  its changelist has no actions. Every admin now uses a `core.admin` base.
- `ScoringConfig.save` raises `ImmutableConfig` when the row is gone (no re-insert).
- `evaluate_ranking --top-n` below 1 → `CommandError`. `--write-baseline --top-n` is specified
  behavior (REC-5).
- `services/evaluation/sheet.py`: `_single_developer` and `_candidate_names` raise `SheetError`
  for a malformed export; `candidate_count(export)`; `import_sheet` validates before unpacking.
- `readme_excerpt`: `html.unescape` after `plain_text`; `_` stripped at word edges, `~` only as
  `~~`; cut at `limit + 1`. Status endpoint: last time from the latest row (3 queries).

**Feedback fixes, review sweep: feedback** (MVP+, fix release)  ✅ shipped in v0.12.53 (no ranking change)

Archived: `openspec/changes/archive/2026-11-03-feedback-review-fixes/` (`skip_specs`; spec
"Recording feedback" edited directly for FD2-6). `Bug_Backlog.md` batch 42 (FB-1, FB-3, FB-5
fixed; FB-2, FB-6 accepted by the owner; FB-4 false positive, FB-7 wontfix). One `/simplify` and
one fix-diff `/code-review` over the combined 0.12.51–0.12.54 code: batch 50 (FD2-1…FD2-9), fixed
before commit. `/security-review` of `feedback/`: nothing.
- `services.feedback.record(user, recommendation, action, *, issue_id=None)`: after
  `_current(lock=True)` one locking query (`select_for_update(of=("self",))` on the issue joined
  to this recommendation's relevant issues). A miss is a race (closed, or dropped by a
  regeneration): no event, `False`, 204, like a recommendation gone; only an issue of another
  repository raises `IssueNotRelevant` (400 `issue_id`). Views never read `RecommendedIssue`.
- `feedback.api._own_recommendation` loads `only("pk", "repository_id")`; services re-read what
  they snapshot. `_current_recommendation(user, repository_id)` also loads the repository, so
  `dismiss` reads once; a repository deleted meanwhile raises `Recommendation.DoesNotExist` → 404.
  A service called from a view must not touch `recommendation.repository` before its re-read.
- SPA: `useSave`/`useUnsave` take `{ id, repositoryId }`; every unsave goes through
  `unsaveRepository` (`DELETE /saved/{repositoryId}`, works after the recommendation is
  regenerated away). `DELETE /recommendations/{id}/save` is kept for API clients only.

**Profiling fixes, review sweep: services/profiling** (MVP+, fix release)  ✅ shipped in v0.12.54 (no ranking change)

Archived: `openspec/changes/archive/2026-11-03-profiling-review-fixes/`. Spec: delta to
`skill-detection` ("README skill evidence", "Dependency evidence", "Contribution evidence");
after the fix-diff review "README skill evidence" and `developer-profile` "Experience level"
were edited directly. `Bug_Backlog.md` batch 43 (PROF-1…PROF-9 fixed; PROF-8 owner decision:
forks never count) and batch 50. `/security-review` of `services/profiling/`: nothing.
`TAXONOMY_VERSION` 2026.11.1; baselines unchanged.
- `ProfileInput.__post_init__` normalizes once for every consumer: `readme` without HTML
  comments, `contributions` without forked repositories (evidence, interests and experience).
  Tests build inputs through `profiling_fixtures.profile(...)` and read `.readme` from it.
- `services.profiling.text.strip_html_comments` (`<!--.*?(?:-->|\Z)`, an unterminated comment
  hides the rest) is the one stripper: `ProfileInput`, `parse_pom`, issue difficulty (`classify`).
- `PhraseMatcher` keys and looks up by `casefold()` and skips a miss: it never raises, whatever
  the text (also used on repository descriptions and issue text).
- `tech_sections` follows CommonMark fences (a run of 3+ backticks or tildes; closed only by the
  same character, at least as long, nothing after it); lines inside are section text, never
  headings. `_ATX` closes only on whitespace + `#`.
- Manifests: `_pep508_names` takes only a list, `_table(value)` for TOML tables; `_PEP508_DIRECT`
  (`name[extras] @ URL`) before the URL skip; `_strip_gradle_comments` matches string literals or
  comments and puts strings back (globs and URLs survive).
- Catalog: one `_sync_catalog(model, catalog, slugs, fields)` in slug order: `in_bulk`, insert
  only missing slugs (`ignore_conflicts`), `bulk_update` rows whose fields differ. An unchanged
  taxonomy costs one read and writes nothing.
- Tests: `make_recommendation` (from `test_models_phase5`), `shared_fixtures.assert_changelist_flat`;
  strings with look-alike letters use `chr()` code points (ruff RUF001).

**Query client fixes, review sweep: frontend/src/app** (MVP+, fix release)  ✅ shipped in v0.12.55 (no ranking change)

Archived: `openspec/changes/archive/2026-11-03-app-review-fixes/`. Spec: delta to `web-client`
("Refresh derived data on job transitions", "Ended session returns to sign-in"). `Bug_Backlog.md`
batch 44 (APP-1…APP-6, APP-9, APP-10 fixed; APP-7, APP-8 accepted). `/simplify` and the fix-diff
`/code-review` were skipped (owner). `/security-review` of `src/app/`: nothing.
- `fetchStatusAndRefresh<S>(queryClient, key, path, signal, refresh)` fetches `path` itself with
  the `queryFn`'s `signal`; an aborted fetch never compares, and a status without a job never
  refreshes. A new status hook passes its path and signal (since the `/simplify` below).
- `useStartSync` awaits `cancelQueries(syncStatusKey)` before `setQueryData`; a new mutation that
  writes a status key must cancel it first.
- `createQueryClient`: a sign-out mutation that fails (not with a 401) refetches `/auth/me`, so a
  session that ended while it was pending ends through the identity's 401; a rejected
  `endSession` resets `signedOut` and puts the cached identity back (CR-7). One flag, `signedOut`.
- `useDataVersions` invalidates once with a `partialMatchKey` predicate. `dataVersions.test.ts`
  scans `src/` (`import.meta.glob` `?raw`) and fails when a `['profile', '<name>'` key is in no
  `AREA_KEYS` area.

**Route fixes, review sweep: frontend/src/routes** (MVP+, fix release)  ✅ shipped in v0.12.56 (no ranking change)

Archived: `openspec/changes/archive/2026-11-03-routes-review-fixes/`. Spec: delta to `web-client`
("Refresh derived data by data versions"; new "Failed refresh keeps the page", "Sync start
errors", "Sign-in page while the identity loads"). `Bug_Backlog.md` batch 45 (ROUTE-1…ROUTE-10;
ROUTE-10 in part, no not-found page). `/simplify` and the fix-diff `/code-review` were skipped
(owner). `/security-review` of `routes/`: nothing.
- Pages gate on `data`, never `isError`/`isSuccess` first: a failed refetch keeps what is shown;
  a failed first load shows an error line (`src/components/Loaded`), never an empty list. New
  pages follow the same order (pending → no data: error → data).
- `SignedInLayout` refetches the versions when `pathname + search + hash` differs from the
  previous route (a ref), never on state-only navigations.
- `RequireAuth` renders `<Outlet context={me.data} />`, `SignedInLayout` passes it on;
  `useSignedInUser()` (`features/auth/api.ts`, `useOutletContext<Me>()`) reads it in any page
  under them.
- `startErrorText(error, at)` (`features/sync/messages.ts`) is the one sync start error text;
  pass the mutation's `submittedAt`. `formatWait` removed.
- `LandingPage` shows "Loading…" while `me.isPending` (since batch 52; was nothing).

**Issue detail fixes, review sweep: features/issues** (MVP+, fix release)  ✅ shipped in v0.12.57 (no ranking change)

Archived: `openspec/changes/archive/2026-11-03-issue-detail-review-fixes/`. Specs: deltas to
`issue-matching` ("Issue detail page"), `recommendation-feedback` ("Feedback events"),
`web-client` ("Failed refresh keeps the page"). `Bug_Backlog.md` batch 46 (FI-1…FI-3, FI-6,
FI-7, FI-10 fixed; FI-4 guard; FI-5, FI-8, FI-9 false positives). `/simplify` and the fix-diff
`/code-review` were skipped (owner). `/security-review` of `features/issues/`: nothing.
- `src/components/ExternalLink` (`href`, `onOpen`): new tab, `noopener noreferrer`, `onOpen` on
  click and middle-button `auxclick`. Every GitHub link that records feedback uses it.
- `src/components/Fact` (`term`, `value`, optional `note`) and `src/lib/format` (`formatDate`,
  `formatDateTime`, `formatTime`): the one copy each; every external link uses `ExternalLink`.
- `/simplify` over the combined 0.12.55–0.12.57 diff (4 agents, one diff; batch 51 of
  `Bug_Backlog.md`): helpers above, `useDataVersions()` without `enabled`, lazy source glob in
  `dataVersions.test.ts`. Skipped: a shared page-state helper for pages outside the diff
  (`RecommendationDetailPage`, `DiscoveryCard`, `SavedPage`, `RecommendationList` still check
  `isError` first; their low-group sweep), the signal names as an OpenAPI enum (API change).
- `features/issues/evidence.ts` `SIGNAL_TEXT` words each difficulty signal; unknown ones are
  dropped. `tests/test_issue_signal_wording.py` (backend) runs `classify.difficulty` and fails
  when its signals differ from the `SIGNAL_TEXT` keys: a new signal needs words on the page.
- `IssueDetailPage` and `RecommendationDetailPage` end with `DeadEnd` only for a 404 or without
  data (batch 45 page order); `src/components/Loaded` (`query`, `failed`, optional `loading`,
  render-prop children) is the shared form for sections and cards (`AppShell`, `DiscoveryCard`).
  Fix-diff `/code-review` of 0.12.55–0.12.57: batch 52 (CR-1…CR-10), fixed before commit. Refetch
  tests must wait after `refetchQueries` (`settle`): TanStack notifies observers on a timer, so
  an assertion right after `act` sees the old render.

**K-1 no longer gates ranking changes** (owner decision, 2026-10-28). Judging `real-a-v2` and
building `benchmark-v2` is optional. A ranking change (B-6, D-11, T-11, † ideas) still needs an
OpenSpec change, must be an improvement on the selection benchmark (`benchmark-v1` until
`benchmark-v2` holds a judged real developer), must not regress on a fresh holdout (add
`holdout-v3` first), and ends with `--write-baseline`. The "Carry-over: K-1 unchanged" lines
above are history.

**Future scope**: verify `docker compose up` from a fresh `.env` (needs a machine with Docker).

**Post-MVP**: personalized or feedback-based ranking, notifications, contribution tracking,
contribution plans, similar repositories, observability dashboards (Sentry, Prometheus, Grafana).

**Ideas** (`ideas.md`, unplanned; each needs an OpenSpec change). Since 0.12.22 ordered by when
an idea can ship. Can ship now (no ranking change), in suggested order:
platform items
(migration round trip), then the interface revamp (§18, owner request:
design direction first, one OpenSpec change per step). Ranking-visible (†, must win on the
selection benchmark and not regress on a fresh holdout): IDF weighting, diversity, stated
preferences, contribution-success signals, opportunity qualifiers,
upstream dependencies, `similar_repo`, content-based `not_code`, and moving the label bands;
whether a ranking change must also be significant is decided once real developers enlarge the
benchmark. Shipped from it in this
series: bootstrap intervals (0.12.19), feedback report (0.12.20), label calibration report
(0.12.21), dismiss reasons (0.12.23), setup readiness (0.12.24), discovery yield report (0.12.25), post-analysis pool cleanup (0.12.26),
data versions (0.12.27), new seeds stored inactive (0.12.28),
rank constraint (0.12.29, T-12), Content Security Policy (0.12.30), JSON report writer (0.12.33, T-14), dependency audit (0.12.34), labeled-issue fetch
(0.12.35), released-name refresh (0.12.36), route-level id validation (0.12.37), browser tests on the production build (0.12.38), config review fixes (0.12.39), core review fixes (0.12.40), accounts review fixes (0.12.41), github review fixes (0.12.42), e2e seed review fixes (0.12.43), services review fixes (0.12.44), GitHub services review fixes (0.12.45), API client review fixes (0.12.46), auth review fixes (0.12.47), jobs review fixes (0.12.48), developers review fixes (0.12.49), repositories review fixes (0.12.50), issues review fixes (0.12.51), recommendations review fixes (0.12.52), feedback review fixes (0.12.53), profiling review fixes (0.12.54), app review fixes (0.12.55), routes review fixes (0.12.56), issue detail review fixes (0.12.57).

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
