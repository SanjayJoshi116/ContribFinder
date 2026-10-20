# ContribFinder

Finds open-source repositories and issues that match a developer's demonstrated skills and
interests. It builds an evidence-backed profile from GitHub and explains every recommendation.

**Version 0.12.4** (job lifecycle and claim fencing: a reclaimed worker can no longer write, lost or crashed jobs recover once and stop at the attempt limit, finished jobs show no running step; MVP+). After signing in with
GitHub, your public profile, README, repositories, dependencies and contributions are synced in
the background and turned into an evidence-backed profile: skills (with the evidence behind each),
interests and languages. From that profile ContribFinder finds and analyzes candidate projects,
then ranks them with deterministic, versioned scoring and shows each recommendation with a match
label (Strong, Good, Partial) and the reasons behind it, never a percentage. You can save or
dismiss projects, refresh everything, and delete your GitHub data or your account at any time
(see the in-app privacy page). Each recommendation also lists the open issues that fit you, with
their contribution type and an estimated difficulty (or "Not enough evidence"). Ranking changes
are measured offline on a hand-judged benchmark before they count as improvements (see
"Evaluating a ranking change"). Semantic matching comes later.

- Stack: Django + DRF + Celery + PostgreSQL (+ Redis), React 19 + TypeScript + Vite.
- What's shipped and planned: [`features.txt`](features.txt). Release notes: [`CHANGELOG.md`](CHANGELOG.md).
- Requirements: `Software Requirements Specification - 2.txt` (authoritative) and `- 1.txt`.
- Engineering guide and roadmap: [`CLAUDE.md`](CLAUDE.md). Specs: `openspec/specs/`; archived
  changes: `openspec/changes/archive/`.

## 1. Register a GitHub OAuth App

GitHub → Settings → Developer settings → OAuth Apps → **New OAuth App**

| Field | Value |
|---|---|
| Homepage URL | `http://localhost:5173` |
| Authorization callback URL | `http://localhost:5173/api/v1/auth/github/callback` |

Copy the **Client ID** and generate a **Client secret**. ContribFinder requests no OAuth scopes;
it reads public data only.

## 2a. Run locally (no Docker)

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/) (`python -m pip install uv` works too; it
doesn't need to be on PATH, and you can set `UV_BIN` to point at it),
Node 24, a local PostgreSQL and, for background jobs, Redis. On Windows, Redis runs inside WSL
(Ubuntu); `npm start` starts it for you. Without Redis the cache is in-process and background
tasks run inline, so GitHub syncs block the request.

Create the database once. `psql` prompts for the `postgres` password:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -c "CREATE ROLE contribfinder LOGIN PASSWORD 'contribfinder' CREATEDB;" -c "CREATE DATABASE contribfinder OWNER contribfinder;"
```

`CREATEDB` lets the test suite create its own `test_contribfinder` database.

Install Redis in WSL once (runs as root, so no sudo password is needed):

```powershell
wsl -d Ubuntu -u root -- apt-get install -y redis-server
```

ContribFinder uses Redis database 1 (`REDIS_URL=redis://localhost:6379/1`), so it doesn't touch
anything else stored in that Redis.

Then:

```bash
npm install        # root: installs the dev runner
npm run setup      # creates .env with generated secrets, installs deps, runs migrations
```

Add `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` from step 1 to `.env`, then:

```bash
npm start          # WSL Redis + Django :8000 + Celery worker + Celery beat + Vite :5173 (proxies /api)
npm run stop       # stop the stack from another prompt (Ctrl+C in its own console also works)
```

Celery beat runs the periodic repository jobs: it marks candidate repositories stale and
refreshes them in the background with the OAuth app's client credentials (never a user's
token). Beat also recovers jobs: a job whose worker died (no heartbeat for
`SYNC_STALE_AFTER_SECONDS`) or whose queued task was lost is requeued once, and a job that used
every `SYNC_MAX_ATTEMPTS` ends as `worker_lost`. Without `REDIS_URL` there is no worker or
beat, so those jobs do not run; syncs then run inline in the request and a GitHub error that
would be retried (rate limit, 5xx) fails the job instead.

Open http://localhost:5173. API health: http://localhost:5173/api/v1/health/.

Django management commands work from the root without uv on PATH:

```bash
npm run manage -- migrate
npm run manage -- reanalyze_profiles   # rebuild profiles from stored data (no GitHub calls)
```

Profile scoring is configurable in `.env` (`EVIDENCE_WEIGHTS` and friends, see `.env.example`).
Run `reanalyze_profiles` after changing it. Repository discovery budgets, filters, staleness and
activity thresholds (`DISCOVERY_*`, `REPO_*`, `ACTIVITY_THRESHOLDS`) are configured the same way.
Every search query runs once per star band (`DISCOVERY_STAR_BANDS`, default 20–999 and 1000+), so
the pool holds smaller projects as well as the most popular ones; `DISCOVERY_MAX_QUERIES` counts
these requests (default 20). Curated lists and documentation repositories (named `awesome-*`,
tagged with a `DISCOVERY_EXCLUDED_TOPICS` topic, or without a detected language) are rejected as
`not_code`.
A completed sync or re-analysis starts a discovery run automatically, and a completed discovery
starts a recommendation generation. Ranking limits and sizes (`RECOMMENDATION_*`,
`RECOMMENDATIONS_TOP_N`, `REPO_SIZE_THRESHOLDS`) and the view de-duplication window
(`FEEDBACK_VIEW_DEDUP_MINUTES`) are in `.env.example` too, as are the issue fetch budget and
difficulty thresholds (`ISSUES_MAX_PAGES`, `ISSUE_*`). Scoring weights and issue matching
parameters live in the active `ScoringConfig` (Django admin); `v2-deterministic` is active.

## Evaluating a ranking change

Ranking changes are measured offline on a fixed benchmark, `apps/backend/evaluation/benchmark-v1.json`:
persona developers with hand-judged candidate repositories (0 not relevant, 1 relevant, 2 highly
relevant). No GitHub calls, no stored data changes.

```bash
npm run manage -- evaluate_ranking --config v1-deterministic --config v2-deterministic
npm run manage -- evaluate_ranking --config v2-deterministic --config-file my-config.json --require-improvement
```

It prints Precision@5, Precision@10, Recall@10, MRR and NDCG@10 per configuration (the first is
the baseline, deltas in parentheses) and every developer's top 10 with judgments (`?` = unjudged).
`--config-file` takes `{"weights": ..., "params": ...}` for a configuration not stored yet;
`--json OUT` writes the full report. A configuration counts as an **improvement** only when its
NDCG@10 is higher than the baseline's and no other metric drops by more than `--tolerance`
(0.01); `--require-improvement` exits non-zero otherwise.

Holdout datasets (`evaluation/holdout-v1.json`, `holdout-v2.json`, four other personas each)
guard against tuning to the benchmark: pass one with `--dataset`. A new configuration replaces the
active one only when it is an improvement over every stored configuration on `benchmark-v1` and
does not regress on the current acceptance holdout by more than the tolerance; a holdout never
chooses between candidates. Once a search has recorded results on a holdout, it cannot accept a
later search's candidate: both existing holdouts are used, so the next search adds `holdout-v3`.

Configurations can opt into these scoring options (no stored configuration uses them yet):
`params.issues.difficulty_fit_mode: "weighted"` (difficulty fit grows with the number and quality
of fitting issues instead of one fitting issue scoring 1.0) and `params.relevance_scaling: true`
(activity, openness and the issue signals count in proportion to how relevant the project is),
plus their own minimum score: `params.min_score` with `params.min_score_basis` `"score"` (the
whole score) or `"relevance"` (the skill, language, framework and interest part only). Without
them, `RECOMMENDATION_MIN_SCORE` applies. `evaluate_ranking --min-score` overrides every
configuration's minimum and says so in the output.

`evaluation/baselines.json` records the stored configurations' metrics per dataset (with the
top N they were computed at), and a test fails when they move. After an intended ranking change,
run `npm run manage -- evaluate_ranking --write-baseline` and commit the file with the change.
Without `--dataset` it rewrites `benchmark-v1`, every other recorded dataset whose file exists,
and the selection benchmark. It merges: `--config v2-deterministic` replaces v2's entries and
keeps v1's. A different `--top-n` must cover every configuration recorded for the dataset, and
`--min-score` is refused (the test recomputes each configuration at its own minimum score).

### Judging real developers

The personas were invented and judged by the same author who designed the ranking, so the
benchmark also takes real developers judged by a person who knows them. Export only accounts whose
owner agreed. Exports and sheets go in the repository's `judging/` folder, which is gitignored
(they are anonymized, but they describe a real person's skills). `npm run manage` runs in
`apps/backend`, so relative paths start there: `../../judging` below is that folder (created if
missing).

1. **Bigger pool.** The local `.env` caps discovery at 10 candidates. For the export, set
   `DISCOVERY_MAX_POOL=40` and `DISCOVERY_MAX_ANALYSES_PER_RUN=40`, run `npm start`, sign in as the
   developer and press **Refresh**; wait until the stage line shows recommendations are done. This
   uses that account's GitHub API budget.
2. **Export** (no GitHub calls; no username, email, GitHub id or token; neutral id):
   ```bash
   npm run manage -- export_benchmark_developer --user-id 2 --as real-a --out ../../judging/real-a.json
   ```
3. **Judge blind.** Write a sheet and grade it in a spreadsheet (2 highly relevant, 1 relevant,
   0 not relevant, blank = not judged; try to grade every row). The sheet shows each repository's
   description, languages, topics, contribution files, activity and open issue count, in
   alphabetical order, and nothing the ranking computed:
   ```bash
   npm run manage -- benchmark_sheet --export ../../judging/real-a.json --out ../../judging/real-a.csv
   ```
4. **Import** the grades (validated; nothing is written on an error). `#` guide lines count only
   above the header; fully blank rows are ignored; a repeated repository or a grade without a
   repository fails naming the row:
   ```bash
   npm run manage -- import_judgments --export ../../judging/real-a.json --sheet ../../judging/real-a.csv
   ```
5. **Build** `benchmark-v2` from the personas and the judged exports (add `--on-conflict first`
   if two exports describe the same repository differently, e.g. exported on different days):
   ```bash
   npm run manage -- build_benchmark --name benchmark-v2 --out evaluation/benchmark-v2.json \
     --input evaluation/benchmark-v1.json --input ../../judging/real-a.json
   ```

Once `benchmark-v2.json` holds a judged real developer, it is the **selection benchmark**:
`evaluate_ranking` uses it by default and reports the persona and real developers' means
separately. Committing it is the judge's decision; if it stays local, the baseline test skips it.

## Your data

The dashboard's "Your data" section and the public `/privacy` page cover what is stored.
**Delete GitHub data** removes everything derived from GitHub (profile, skills, recommendations,
saved and hidden projects, feedback, job history) and keeps your account, so you can sync again.
**Disconnect GitHub** revokes ContribFinder's authorization and deletes the same data.
**Delete account** does both and removes the account. None of these touch your GitHub account
itself.

## 2b. Run with Docker

```bash
cp .env.example .env    # or reuse the .env from `npm run setup`
docker compose up --build
```

Compose runs its own Postgres (host port 5433) and Redis, and overrides `DATABASE_URL` and
`REDIS_URL` with container hostnames, so the same `.env` works for both modes. If you copied
`.env.example`, fill in `DJANGO_SECRET_KEY` and `TOKEN_ENCRYPTION_KEYS` yourself (commands
are in the file).

## Deploying behind a proxy

Production settings (`config.settings.production`) refuse to start the web server, Celery
worker or beat when a system check reports an error (for example empty `TOKEN_ENCRYPTION_KEYS`).
Set `NUM_PROXIES` to the number of proxies you control in front of Django (usually 1 for a
TLS-terminating load balancer). With `0`, forwarded headers are ignored: every client behind the
proxy shares one throttle bucket and HTTPS detection fails, so the SSL redirect loops (system
check `core.W002` warns about this). `/api/v1/health/` is never throttled or redirected, so
probes can use plain HTTP.

## Secrets

`TOKEN_ENCRYPTION_KEYS` encrypts stored GitHub tokens. To rotate, put a new key first
(`new,old`); old tokens still decrypt. If every key is lost, users just sign in again.
Never commit `.env`.

## Tests

`uv run pytest` in `apps/backend` (uses local PostgreSQL) and `npm test` in `apps/frontend`.
All commands are in `CLAUDE.md` §6.

## Known issues

`Bug_Backlog.md` lists the findings of a full codebase review (2026-10-19), each verified against
the code (confirmed, partial or false positive), grouped into 11 fix batches in priority order.
Batch 1 (security hardening) shipped in 0.12.1, batch 2 (privacy and deletion finality) in
0.12.2, batch 3 (evaluation tooling integrity) in 0.12.3, batch 4 (job lifecycle and claim
fencing) in 0.12.4.

## Versioning

`VERSION` is the single source of truth. Keep `package.json`, `apps/frontend/package.json` and
`apps/backend/pyproject.toml` in sync; `npm run check:version` (also run in CI) verifies it.
Before the MVP, each completed roadmap phase bumps the minor version; fix releases bump the patch
version.
