## Why

The full review sweep of `scripts/` (batch 48 of `Bug_Backlog.md`, SCR-1…SCR-10) found that
`npm run stop` can kill a sibling checkout's stack and unrelated Vitest or pytest processes,
loses the records of processes it cannot read, that the Redis runner exits 0 when Redis never
comes up (so the stack keeps running without it) and crashes on a failed keep-alive spawn, and
smaller issues in the POSIX child stop, IPv6 Redis URLs, uv lookup order and repeated root
computations.

## What Changes

- **SCR-1**: path matching needs the repository root followed by a path separator, so
  `ContribFinder-v2` is never this repository.
- **SCR-2**: only the stack's own programs match by path: Vite's `vite/bin/vite.js` (never
  `vitest`), Celery run as the `celery` program or `-m celery` (never a path that merely contains
  "celery"), Django's `manage.py runserver`.
- **SCR-3**: on Windows every process is listed, also those whose command line cannot be read; a
  record whose process is alive but unreadable is kept (not deleted as stale), the process is left
  running and `npm run stop` reports it.
- **SCR-4**: on POSIX, a child started without its own process group (`detached: false`) is
  signalled directly instead of through a group it does not lead.
- **SCR-6**: the Redis runner exits 1 when Redis never becomes reachable, so `concurrently` stops
  the rest of the stack.
- **SCR-7**: a keep-alive spawn failure is logged and fails the runner with a readable message,
  never an unhandled `'error'` event.
- **SCR-8**: an IPv6 `REDIS_URL` host (`[::1]`) is read without brackets.
- **SCR-9**: Python install folders are searched newest version first (`Python313` before
  `Python39`).
- **SCR-10**: `setup.mjs`, `backend.mjs` and `manage.mjs` import `root` from `env.mjs`.
- Accepted: **SCR-5** (a grandchild orphaned when the direct child exits first): not reproduced,
  and `npm run stop` already stops this repository's Django, Celery and Vite by path.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `developer-tooling`: "Stopping the local stack stops only this repository" (sibling checkout,
  other programs, unreadable processes), "Local Redis stays reachable while the stack runs"
  (unreachable Redis and spawn failures fail the runner), "Backend commands find uv without PATH"
  (newest install first).

## Impact

- `scripts/stack.mjs`, `stop.mjs`, `child.mjs`, `redis.mjs`, `env.mjs`, `uv.mjs`, `setup.mjs`,
  `backend.mjs`, `manage.mjs`, and their `*.test.mjs`.
- No app, backend or API change. Checked by `npm run test:scripts`, `lint:scripts`,
  `format:scripts`; a manual `npm start` / `npm run stop` round on Windows.
