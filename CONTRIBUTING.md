# Contributing to ContribFinder

Thanks for your interest. ContribFinder matches developers to open-source contribution
opportunities from evidence in their GitHub data, and explains every match. This file covers how to
set up, what to check before a pull request, and the rules the code has to keep.

Security problems: do not open a public issue; see [`SECURITY.md`](SECURITY.md).

## Before you start

- **Open an issue first** for anything bigger than a small fix, so we can agree on the approach
  before you spend time on it.
- **Behavior changes are specified first.** Accepted behavior lives in `openspec/specs/`; a change
  to it starts as an OpenSpec change under `openspec/changes/` (proposal, design, spec deltas,
  tasks). Read the spec of the capability you touch before changing it.
- **Ranking changes have a higher bar.** Anything that can change which repositories are
  recommended, or in which order, needs its own OpenSpec change, must be an improvement on the
  selection benchmark, must not regress on a fresh holdout, and ends with an updated
  `baselines.json`. See the README section "Evaluating a ranking change".
- **No AI calls in the MVP.** The ranking is deterministic; nothing may call an LLM or embedding
  API (`services/ai/` holds interfaces only).

## Set up

Follow the README: register a GitHub OAuth App (section 1), then "Run locally (no Docker)"
(section 2a). In short, with PostgreSQL running and its `contribfinder` role and database
created:

```
npm run setup   # .env with generated secrets, dependencies from the lockfiles, migrations
npm start       # Django on :8000, Vite on :5173, Celery and Redis
```

You need Python 3.12+ with [`uv`](https://docs.astral.sh/uv/), Node 24 and PostgreSQL. Redis is
optional locally (without `REDIS_URL`, tasks run inline).

## Where code goes

The repository is a monorepo: `apps/backend` (Django, DRF, Celery) and `apps/frontend` (React,
TypeScript, Vite), plus the npm runners in `scripts/`. `CLAUDE.md` §4 maps every folder.

- Business logic lives in `apps/backend/services/`. Views, serializers and Celery tasks are thin
  wrappers that call services.
- Only `services/github/` talks to GitHub. Everything that calls GitHub, or runs long, runs in a
  Celery task; an HTTP request never waits on GitHub.
- Every endpoint is under `/api/v1/`, enforces per-user authorization, is paginated when it
  returns a list, and appears in the OpenAPI schema. Errors use the
  `{"error": {code, message, details?}}` envelope.
- Frontend API types are generated, never written by hand: after any API change run
  `npm run api:sync` in `apps/frontend` and commit both `src/api/openapi.json` and
  `src/api/schema.d.ts`.
- Explanations come only from computed signals; the UI shows match labels (Strong / Good /
  Partial), never a percentage.

## Secrets and user data

- GitHub tokens and other secrets are never returned to the browser, logged, put in URLs or
  committed. Never commit `.env`.
- A new model that stores user data must be deleted by the data deletion routine (or kept on
  purpose) and named on the privacy page; `tests/test_privacy_coverage.py` fails until it is.

## Tests and checks

Run the checks for the parts you changed before opening a pull request. CI runs all of them.

Backend (`apps/backend`):

```
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest
```

Frontend (`apps/frontend`):

```
npm run lint
npm run format:check
npm run build        # type-checks too
npm test
```

Runner scripts (repository root):

```
npm run test:scripts
npm run lint:scripts
npm run format:scripts
```

Browser tests (`npm run e2e` in `apps/frontend`, see the README section "End-to-end tests") are
needed when you change a browser flow, an e2e spec or its runner.

Test rules:

- Every service stage has unit tests.
- Tests never call the live GitHub API: use recorded fixtures and mock HTTP with `respx`.
- A bug fix comes with a test that fails without it.

## Dependencies

- Installs come from the committed lockfiles (`npm ci`, `uv sync --locked`); CI fails when a lock
  is stale. After changing `pyproject.toml` run `uv lock`; after changing a `package.json`, update
  its `package-lock.json` with `npm install`.
- `npm run audit:deps` checks every lockfile for known vulnerabilities. A new dependency must
  pass it.
- Prefer the standard library and what the project already uses over a new dependency.

## Pull requests

- Branch from `main`; keep one topic per pull request.
- Write commit messages in the existing style: a type, a colon and a short summary
  (`fix: ...`, `feat: ...`, `docs: ...`), then a body that says why.
- Describe what changed and how you tested it. Link the issue and the OpenSpec change, if any.
- Add an entry under `[Unreleased]` in `CHANGELOG.md` for any change a user or operator would
  notice.
- Version numbers, `features.txt` and the release notes are updated by the maintainer when a
  change is released.

## License

ContribFinder is released under the [MIT License](LICENSE). By contributing, you agree that your
contribution is released under the same license.
