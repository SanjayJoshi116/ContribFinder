## 1. Stopping the stack

- [x] 1.1 SCR-1: whole-folder root match in `ownedByPath` (D1).
  - Test: a sibling `…ContribFinder-v2` Django/Vite is not killed.
- [x] 1.2 SCR-2: program shapes for Vite, Celery and Django (D2).
  - Tests: Vitest worker, pytest `tests/test_celery_config.py`, a `-m celery` worker, the
    `celery` executable path; existing matches unchanged.
- [x] 1.3 SCR-3: unreadable command lines kept as `unknown` (D3); `stop.mjs` lists every Windows
  process and reports unknowns.
  - Test: a live recorded pid with `cmd: null` is neither killed nor removed, and is in `unknown`.

## 2. Runners

- [x] 2.1 SCR-4: direct signal for a non-detached child on POSIX (D4).
  - Test (POSIX only, skipped on Windows): `runChild` with `detached: false` stops its child on
    SIGTERM.
- [x] 2.2 SCR-6, SCR-7: Redis runner `stop(1)` on wait failure; `'error'` handler on the
  keep-alive (D5).
- [x] 2.3 SCR-8: brackets stripped from an IPv6 `REDIS_URL` host (D6).
  - Test: `redis://[::1]:6379/1` → host `::1`, local.
- [x] 2.4 SCR-9: newest Python install first (D6).
  - Test (`uv.test.mjs`): `newestPythonFirst` orders 313, 312, 39, then other names.
- [x] 2.5 SCR-10: `root` from `env.mjs` in `setup.mjs`, `backend.mjs`, `manage.mjs` (D6).

## 3. Backlog

- [x] 3.1 `Bug_Backlog.md` batch 48: SCR-1…SCR-4, SCR-6…SCR-10 fixed (0.12.59); SCR-5 accepted;
  sweep text updated.

## 4. Checks

- [x] 4.1 `npm run test:scripts`, `npm run lint:scripts`, `npm run format:scripts`.
- [x] 4.2 Manual on Windows: `npm start`, then `npm run stop` from a second prompt stops the
  stack and says nothing is left; `npm run stop` again says "Nothing to stop."
- [x] 4.3 `openspec validate scripts-review-fixes --strict`.

## 5. Release

- [x] 5.1 `/simplify`, then `/code-review` on the fix diff; record and fix (or the owner skips
  this step) — skipped by the owner (2026-11-03).
- [x] 5.2 Archive (syncs the `developer-tooling` delta); release housekeeping (CLAUDE.md §8,
  0.12.59); commit only when the owner says so.
