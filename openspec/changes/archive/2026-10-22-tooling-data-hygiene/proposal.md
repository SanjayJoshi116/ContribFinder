## Why

Batch 16 of `Bug_Backlog.md` (P-1…P-5) and the open `/simplify` skips Q-10…Q-12 from
`performance-cleanup`, re-checked against the code on 2026-10-22. They are local-tooling gaps and
small data-access leftovers that cost time in normal work:
- the stack can shut itself down when the WSL keep-alive ends unexpectedly (P-1);
- `npm run format:check` fails on every Windows checkout (P-2);
- two frontend tests failed once under load (P-3);
- `npm run api:sync` needs `uv` on PATH, unlike every other command (P-4);
- the runner scripts have no lint or format check (P-5);
- reading a repository's newest snapshot still sorts all of its snapshots (Q-10);
- the "newest snapshot" order is written by hand in three places (Q-11);
- one-line metadata wrappers and a test import shim are left over (Q-12).

None of this changes ranking, so it does not wait for K-1. Batch 8 still waits for K-1.

## What Changes

- **The Redis runner survives a lost keep-alive (P-1).** When the WSL keep-alive exits while
  the stack is running, the runner logs the exit code (hex as well), starts a new keep-alive and
  records it. After 3 restarts within 5 minutes it fails as it does today. An intended stop never
  restarts it.
- **LF line endings in the repository (P-2).** A `.gitattributes` makes Git check out text
  files with LF on every platform, so the format checks pass on Windows. Existing checkouts
  need one renormalizing checkout (README).
- **No flaky frontend tests (P-3).** Find the two tests that fail under load and make them wait
  on the right signal.
- **`npm run api:sync` finds `uv` like other commands (P-4).** `api:export` goes through
  `scripts/manage.mjs`.
- **Runner scripts are linted and formatted (P-5).** ESLint and Prettier configs at the root
  cover `scripts/*.mjs`. New `npm run lint:scripts` and `npm run format:scripts`, and CI runs
  both.
- **Newest snapshot read from the index (Q-10, Q-11).**
  - The snapshot index gains the `-id` tie-break, so the newest-snapshot order is a plain
    index scan.
  - One shared ordering constant replaces the three copies of that order.
- **Leftovers removed (Q-12).**
  - The `_update_metadata` wrappers go: callers use `merge_metadata` directly.
  - Tests import the database builders from `e2e.builders` directly, and the re-export in
    `tests/repo_fixtures.py` goes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `developer-tooling`:
  - New requirement: the local Redis stays reachable while the stack runs.
  - New requirement: formatting and lint checks pass on every platform and cover the runner
    scripts.
  - New requirement: every npm command that runs backend code finds `uv` without PATH.

## Impact

- Scripts: `scripts/redis.mjs`, a new pure restart-budget helper with its test, root
  `package.json` (lint/format scripts, devDependencies `eslint`, `@eslint/js`, `globals`,
  `prettier`), root `eslint.config.mjs` and `.prettierrc.json`, `.prettierignore`.
- Repository: new `.gitattributes`, and the one-time renormalization of line endings in the
  index (no content change).
- CI: `.github/workflows/ci.yml` runs the root lint and format checks.
- Frontend: `apps/frontend/package.json` (`api:export`), and the flaky tests found.
- Backend:
  - `repositories/models.py` and a new migration (index change);
  - `repositories/queries.py` (the ordering constant), `repositories/api.py`,
    `services/repositories/analysis.py`;
  - `services/github/sync.py`, `services/discovery/service.py`;
  - the test modules that import builders.
- No API, ranking or UI change. Patch release 0.12.11.
