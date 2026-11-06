## Why

The full review sweep of `.github/workflows/` (batch 49 of `Bug_Backlog.md`, CI-1…CI-10) found
that CI can pass on a dependency resolution that was never committed, skips the built-index CSP
test, misses untracked generated files, downloads the API type generator outside any lockfile,
runs third-party actions by mutable tag with the job token left in `.git/config`, loses the
Playwright report when the job times out, never runs the runner tests on Windows, and repeats
work (type check twice, Chromium re-downloaded on every release bump). The repository is public,
so the supply-chain rows matter even with a read-only token.

## What Changes

- **CI-1**: every `uv` command in CI uses the committed lock as is (`uv sync --locked`,
  `UV_LOCKED: 1` for the `uv run` steps); a `pyproject.toml` change without `uv lock` fails. The
  `check-version.mjs` comment is corrected.
- **CI-2, CI-10**: the frontend job builds before testing, so the built-index CSP test runs; the
  separate type check goes (the build type-checks).
- **CI-3**: the drift check also fails on untracked files under `apps/frontend/src/api`.
- **CI-4**: `openapi-typescript` becomes a pinned dependency of its own tree
  `apps/frontend/tools/api-types/` (locked and audited; it needs TypeScript 5, the app 6);
  `gen:api` calls that binary instead of `npx --yes`.
- **CI-5**: every action is pinned to a full commit SHA with its version as a comment; Dependabot
  keeps the actions current (weekly).
- **CI-6**: every checkout sets `persist-credentials: false`.
- **CI-7**: the browser tests get their own step timeout, and the report plus traces
  (`test-results/`) upload on failure or cancellation.
- **CI-8**: a `windows-latest` job runs `npm run test:scripts`.
- **CI-9**: the Playwright browser cache is keyed on the installed Playwright version.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `developer-tooling`: new requirements "CI installs the committed locks", "CI runs pinned
  third-party code without a stored token", "Runner tests run on Windows and Linux" and "Browser
  test reports survive a timeout".

## Impact

- `.github/workflows/ci.yml`, `audit.yml`, new `.github/dependabot.yml`,
  `apps/frontend/package.json` (`gen:api`), new `apps/frontend/tools/api-types/` (package and
  lockfile), `scripts/setup.mjs`, `scripts/audit.mjs`, `scripts/check-version.mjs` (comment).
- The owner runs one `npm install --allow-remote=all` in `apps/frontend/tools/api-types` (the
  local npm refuses remote installs otherwise); it writes the lockfile.
- No app, backend or API change. Verified by `npm run api:sync` (no drift with the local
  generator), the frontend and script checks, and the first CI run on `main`.
