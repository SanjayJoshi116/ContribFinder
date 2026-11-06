## Context

Findings: `Bug_Backlog.md` batch 49. Jobs: `backend`, `frontend`, `api-contract` (versions,
script tests, `api:sync` drift), `e2e`; `audit.yml` (`npm run audit:deps`). `permissions:
contents: read`, no secrets. The local npm has `allow-remote=none` (CLAUDE.md §6): adding a
dependency needs the owner's `--allow-remote=all` install.

## Goals / Non-Goals

**Goals:** reproducible installs, pinned third-party code, no stored token, Windows coverage for
the runners, reports kept on timeout, less repeated work.

**Non-Goals:** moving actions to new majors (Dependabot proposes those as separate PRs);
injectable `platform` in the runners (CI-8 runs the existing tests on Windows as they are).

## Decisions

**D1. Locked uv (CI-1).** `uv sync --locked` in every job and `env: UV_LOCKED: "1"` at workflow
level (covers `uv run` inside npm scripts such as `api:export`). `--locked` checks the lock
against `pyproject.toml`; `--frozen` did not. The `check-version.mjs` comment says `npm ci` and
`uv sync --locked` reject stale locks. `audit.yml` keeps `uv export --frozen` (it only reads the
lock; the audit checks what is locked).

**D2. Build, then test (CI-2, CI-10).** Frontend job: Lint, Format, Build (`tsc -b && vite
build`), Tests. The Type check step goes. `csp.config.test.ts` then finds `dist/index.html`.

**D3. Untracked drift (CI-3).** Fail when `git status --porcelain -- apps/frontend/src/api` prints
anything, showing that status.

**D4. Locked generator in its own tree (CI-4).** `openapi-typescript@7.13.0` needs TypeScript
`^5`, the app is on 6 (`npm install` in `apps/frontend` fails with ERESOLVE; `--legacy-peer-deps`
would have to apply to every install). So `apps/frontend/tools/api-types/` is its own package
(`openapi-typescript` 7.13.0 and `typescript` 5.9.3, exact) with its own lockfile: `gen:api` runs
its binary through `node`, CI runs `npm ci` there in `api-contract`, `npm run setup` installs it,
and `scripts/audit.mjs` audits it as a third npm tree. The owner runs its first install; then
`npm run api:sync` must leave no drift (same generator version as before). Alternatives: npm
`overrides` (peer ranges are not reliably overridden, and the generator would run on an
unsupported TypeScript), or keeping `npx` (unlocked transitive dependencies).

**D5. SHA pins (CI-5).** Each `uses:` becomes `owner/action@<40-hex sha> # vX.Y.Z`, the commit of
the newest tag of the major in use (from `git ls-remote --tags`, annotated tags peeled with
`^{}`). `.github/dependabot.yml`: `package-ecosystem: github-actions`, directory `/`, weekly. npm
and pip updates stay manual (the audit covers advisories).

**D6. No stored token (CI-6).** `with: persist-credentials: false` on every `actions/checkout`
(no step pushes or fetches after checkout).

**D7. Reports on timeout (CI-7).** "Browser tests" gets `timeout-minutes: 20` (the job keeps 30);
the upload runs `if: ${{ failure() || cancelled() }}` and uploads `apps/frontend/playwright-report/`
and `apps/frontend/test-results/` (`if-no-files-found: ignore`). A step timeout fails the step, so
`failure()` holds and the artifact is kept.

**D8. Windows runner tests (CI-8).** Job `scripts-windows` on `windows-latest`: checkout,
setup-node 24 with the root lockfile cache, `npm ci`, `npm run test:scripts`. Lint and format stay
on Linux (`.gitattributes` keeps LF everywhere).

**D9. Browser cache by version (CI-9).** A step writes `npx playwright --version` to an output;
the cache key is `playwright-${{ runner.os }}-<version>`.

## Risks / Trade-offs

- [Pinned SHAs go stale] → Dependabot weekly; the version comment shows what is pinned.
- [The Windows job adds minutes] → Only the script tests (seconds) plus `npm ci` of the root.
- [`UV_LOCKED` changes local habits] → CI only; local commands are unchanged.
