## 1. Installs

- [x] 1.1 CI-1: `uv sync --locked` everywhere, `UV_LOCKED: "1"` at workflow level in `ci.yml`;
  correct the `check-version.mjs` comment (D1).
- [x] 1.2 CI-4: `apps/frontend/tools/api-types/` (generator and TypeScript 5, exact); the owner
  runs `npm install --allow-remote=all` there (writes its lockfile); `gen:api` runs its binary;
  CI `npm ci` there; `setup.mjs` installs it; `audit.mjs` audits it (D4).
  - `npm run api:sync` leaves `src/api` unchanged.

## 2. Jobs

- [x] 2.1 CI-2, CI-10: frontend job order Lint, Format, Build, Tests; Type check step removed (D2).
- [x] 2.2 CI-3: drift check with `git status --porcelain` (D3).
- [x] 2.3 CI-7: step timeout on Browser tests; upload on failure or cancel, report and traces (D7).
- [x] 2.4 CI-8: `scripts-windows` job (D8).
- [x] 2.5 CI-9: Playwright cache key from the installed version (D9).

## 3. Hardening

- [x] 3.1 CI-5: every `uses:` pinned to a commit SHA with a version comment, in `ci.yml` and
  `audit.yml`; `.github/dependabot.yml` for GitHub Actions (D5). Pins: checkout v4.4.0,
  setup-uv v6.8.0, setup-node v4.4.0, cache v4.3.0, upload-artifact v4.6.2 (`git ls-remote`).
- [x] 3.2 CI-6: `persist-credentials: false` on every checkout (D6).

## 4. Backlog

- [x] 4.1 `Bug_Backlog.md` batch 49: CI-1…CI-10 fixed (0.12.60); sweep table and open items (the
  medium group done).

## 5. Checks

- [x] 5.1 Workflow YAML parses (load `ci.yml`, `audit.yml`, `dependabot.yml`); every `uses:`
  matches `@[0-9a-f]{40} # v`.
- [x] 5.2 Frontend: `npm test`, `npm run lint`, `npm run typecheck`, `npm run format:check`,
  `npm run build`; `npm run test:scripts`, `lint:scripts`, `format:scripts`;
  `npm run check:version`; `npm run audit:deps` (the new devDependency).
- [x] 5.3 `openspec validate ci-review-fixes --strict`.
- [ ] 5.4 After the owner pushes: the CI run on `main` is green, `scripts-windows` included.

## 6. Release

- [x] 6.1 `/simplify`, then `/code-review` on the fix diff; record and fix (or the owner skips
  this step). `/simplify` run (batch 53) and fix-diff `/code-review` (batch 54), both applied.
- [x] 6.2 Archive (syncs the `developer-tooling` delta); release housekeeping (CLAUDE.md §8,
  0.12.60); commit only when the owner says so.
