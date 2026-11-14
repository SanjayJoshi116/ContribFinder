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
- Each phase (history in `CLAUDE_HISTORY.md`) is specified in detail as an OpenSpec change under `openspec/changes/`
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
│                         app's Content-Security-Policy and its build-only Vite plugin);
│                         tools/api-types/ (locked OpenAPI type generator, its own npm tree)
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
├─ LICENSE (MIT), SECURITY.md (private vulnerability reporting), CONTRIBUTING.md (setup, checks,
│  rules and pull requests for outside contributors; keep it in step with §3, §5 and §6)
├─ VERSION, CHANGELOG.md, features.txt, Bug_Backlog.md (verified findings, fix batches),
│  ideas.md (unplanned gap analysis by when it can ship: no ranking change first, then
│  ranking-visible ideas; each idea needs an OpenSpec change first); reports/ (gitignored --json
│  outputs)
└─ .github/workflows/ci.yml, audit.yml (dependency audit: PRs, main, weekly, on demand);
   dependabot.yml (GitHub Actions pins, weekly)
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
- `npm run test:scripts`: Node built-in tests for the runners (`scripts/*.test.mjs`, also in CI
  on Linux and Windows; they import only Node built-ins and `./*.mjs`, so CI's Windows job
  installs nothing).
  `npm run lint:scripts` / `format:scripts`: ESLint and Prettier for `scripts/` (also in CI).
  `.gitattributes` keeps LF in every checkout; a Windows checkout from before 0.12.11 refreshes
  its working files once (README).
  `npm run setup` uses `npm ci` (never rewrites a lockfile); `npm run check:version` also checks
  `packages[""].version` of both npm lockfiles.
- `npm run audit:deps` (`scripts/audit.mjs`, CI workflow `audit.yml`): `pip-audit` (pinned,
  through `uv tool run` on `uv export --frozen`) and `npm audit` for `apps/frontend`,
  `apps/frontend/tools/api-types` and the root. Fails on any Python advisory and npm high/critical, unless accepted in
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
  `src/api/schema.d.ts`. Run it after any API change and commit both files; CI fails on drift
  (untracked files too). The generator is `apps/frontend/tools/api-types/` (`openapi-typescript`
  with TypeScript 5, exact, own lockfile; the app is on TypeScript 6), installed by `npm run setup`.
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

## 7. Status and roadmap

Current: **v0.12.68**. Phases 1–5, 7, 8a, 8b shipped; MVP definition of done (SRS-2 §82) met
in v0.6.0. The full per-release record (phase FRs, deviations as built, carry-overs, every fix
release since 0.12.1) lives in **`CLAUDE_HISTORY.md`**: read the entry for an area before
changing it. Per-release detail also in `CHANGELOG.md`; accepted behaviour in `openspec/specs/`.

New work: one OpenSpec change per phase or fix batch before implementing. `Bug_Backlog.md` holds
verified findings and fix batches (review sweep workflow there).

**Ranking changes** (owner decision 2026-10-28, K-1 no longer gates): need an OpenSpec change,
must be an improvement on the selection benchmark (`benchmark-v1` until `benchmark-v2` holds a
judged real developer), must not regress on a fresh holdout (add `holdout-v3` first), and end
with `--write-baseline`. Judging `real-a-v2` / building `benchmark-v2` is optional.

**Next** (`ideas.md`, each needs an OpenSpec change). Can ship now (no ranking change): platform
items (migration round trip), then the interface revamp (§18, owner request: design direction
first, one OpenSpec change per step). Ranking-visible (†): IDF weighting, diversity, stated
preferences, contribution-success signals, opportunity qualifiers, upstream dependencies,
`similar_repo`, content-based `not_code`, moving the label bands. Whether a ranking change must
also be significant is decided once real developers enlarge the benchmark.

**Future**: Phase 6 semantic matching (`services/ai/` interfaces, pgvector, `EMBEDDED` state, AI
failure falls back to deterministic); verify `docker compose up` from a fresh `.env`.
**Post-MVP**: personalized/feedback-based ranking, notifications, contribution tracking and
plans, similar repositories, observability (Sentry, Prometheus, Grafana).

### Rules learned in past releases

Durable rules from the history; the release that introduced each is in `CLAUDE_HISTORY.md`.

Jobs and locking:
- Job services: `claim_job` → pass the claimed job object (never an id) to `job_write`,
  `save_progress` (steps), `merge_metadata` (metadata), `heartbeat`, `finish_job`. Fetch before
  `job_write`; no I/O under the lock. `job_guard.stale_before` / `lost_before` / `is_stalled` are
  the one cutoffs; `JobStatus` / `ACTIVE_STATUSES` the one active list.
- Lock order (`services/locks.py`): job → `lock_developer` → dismissals/saves → recommendations →
  issues by pk → children. New writers of recommendation or feedback rows follow it. Bulk
  repository locks in GitHub ID order (`storage.lock_for_upsert` before a batch of upserts).
- Eager Celery = last attempt: `retry.attempt_number(..., eager=)`. Retry-path tests use
  `override_settings(CELERY_TASK_ALWAYS_EAGER=False)`.
- Feedback events never reference a recommendation that may be gone; services re-read what they
  snapshot (`_current`), so a service called from a view must not touch
  `recommendation.repository` before its re-read.

GitHub and data:
- Public client methods raise typed errors (`GitHubInvalidResponse` for bad JSON); callers never
  catch bare `KeyError`/`ValueError`. `errors.error_for_response` is the one status mapping;
  `client._api_origin` the one origin check; `client.parse_dt` the one time parser.
- Raw-file readers use `_Response.content` (cleaned by `storable`), never `.text`.
- Revoke tokens only through `accounts.queue_revocation`; nothing on the request path calls GitHub.
- Repository rows are never deleted for a name (`lifecycle.release_name`); eligibility and
  RECOMMENDABLE/INDEXED change only in `services/repositories/lifecycle.py`. Newest snapshot via
  `repositories.queries.latest_snapshot`; current activity via `features.current_activity` /
  `with_current_activity` (kept in step by a test). Setup facts are shown, never scored.
- One text helper each: `profiling/text.strip_html_comments`, `FENCE`/`strip_code_fences`,
  `labels.parts` (label parser; a new scope word must not clash with aliases),
  `IssueInput(max_chars=)` before `classify.difficulty` / `technologies.detect`.
- A new difficulty signal needs words in `features/issues/evidence.ts` `SIGNAL_TEXT` (test).
- Scoring configs are immutable once stored; new seeds after v2 use `migrations/_seeding.py`
  (stored inactive); activation only through `activate_scoring_config`.
- New user-linked model: deleted by `delete_github_data` or kept on purpose, category on
  `PrivacyPage.tsx` (`test_privacy_coverage.py`).

Backend conventions:
- Settings: comma lists `env_list`, JSON `env_json`/`env_mapping` (never bare `env.list`/`env.json`).
  A new numeric setting needs a system check (`core/checks.py`).
- Admins use a `core.admin` base; job-written data uses `ViewOnlyAdmin`.
- Management commands writing JSON use `core.reports.write_json`.
- Test fixtures shared by import live in `tests/shared_fixtures.py`, not `conftest.py`. Register
  labeled `respx` routes before generic ones. A test double of `load_candidates` accepts
  `**kwargs`; a fixture storing an activity label stores data that gives it.

Frontend:
- One query client (`createQueryClient`); status keys under `['jobs']` (sync: `['sync','status']`),
  never under a prefix their own job invalidates. A new `['profile', ...]` query goes in an
  `AREA_KEYS` area (test). Call `useDataVersions` from one component only.
- New status hook passes its path and signal to `fetchStatusAndRefresh`; a mutation writing a
  status key cancels it first. Sign-out flows set `ENDS_SESSION_META_KEY` and use
  `leaveSignedIn`; account mutations use `accountMutationKey`.
- Pages gate on `data` first (pending → no data: error → data), via `src/components/Loaded`.
- A detail route wraps its page in `RouteId`. Lazy components only via `src/app/lazyLoaders.ts`.
- A list link into a detail page passes `listState(location.search)`; the page returns
  through `listPath(location.state)` (`features/recommendations/navigation.ts`).
- `apiFetch` JSON callers use `json:` (never a hand-built header). External links use
  `ExternalLink`; dates `src/lib/format`.
- A mutation started from a component an optimistic update unmounts uses `mutateAsync`.
- New script, image or API origin goes in `csp.config.ts`. Refetch tests wait (`settle`) after
  `refetchQueries`. Playwright: data-changing specs own a seeded user (`MUTATING_USERS`); match
  exact names (`{ name: 'Dismiss', exact: true }`).

Scripts and CI:
- A new runner calls `recordProcess()`; a library script calls `refuseRun`; CLIs guard with
  `isMain`. Programs found by path need a shape in `stack.mjs` plus a test. Script tests import
  only Node built-ins and `./*.mjs`.
- A new npm tree goes in `env.mjs` `NPM_TREES` and `ci.yml`. Every `uses:` pinned to a 40-hex
  sha with `# vX.Y.Z`; checkouts `persist-credentials: false`. CI runs `uv sync --locked`.
- Shell heredocs in Claude Code's Bash here turn `\\` into `\`: write backslash content with
  Edit/Write.

## 8. Release housekeeping

When a change (phase) is completed and archived, update in the same commit:
1. `VERSION`, root `package.json`, `apps/frontend/package.json`, `apps/backend/pyproject.toml`
   (then refresh lockfiles: `npm install` / `uv lock`). Before the MVP, each phase bumps the minor
   version (`0.x.0`), and fixes bump the patch version. `npm run check:version` must pass (it also
   checks `package-lock.json`, `apps/frontend/package-lock.json` and `apps/backend/uv.lock`).
2. `CHANGELOG.md`: move `[Unreleased]` entries into a dated version section (Keep a Changelog).
3. `features.txt`: flip shipped items to `[x]`, and mark carry-overs `[~]`.
4. `README.md`: version/status line, plus any setup changes.
5. `CLAUDE.md` §7: current version and next items, plus any new durable rule; append the full
   release entry (deviations, carry-overs) to `CLAUDE_HISTORY.md`.

The API contract version (`/api/v1`, OpenAPI `1.0.0`) changes only on breaking API changes,
independently of the app version.
