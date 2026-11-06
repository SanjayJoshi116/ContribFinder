## Context

Findings: `Bug_Backlog.md` batch 48. `stop.mjs` lists processes (PowerShell `Get-CimInstance`
on Windows, `ps` elsewhere) and calls the pure `matchStack(processes, records, repo, selfPid)`
in `stack.mjs` with `repo = root.toLowerCase()`; `ownedByPath` matches by executable plus a
substring test on the command line. `runChild` (`child.mjs`) spawns detached on POSIX and
signals the group; `e2e-backend.mjs` passes `detached: false`.

## Goals / Non-Goals

**Goals:** keep `matchStack` pure and tested for every new rule; fail the Redis runner loudly.

**Non-Goals:** SCR-5 (orphaned grandchild on Windows; accepted, see proposal); a Windows CI job
for the runners (batch 49, CI-8).

## Decisions

**D1. Whole-folder match (SCR-1).** `ownedByPath` normalizes the command line and the root to
`/` and lowercase, and requires `root + '/'`. `matchStack` gets the root as given and normalizes
once.

**D2. Program shapes (SCR-2).** In the normalized command line:
- node: `/node_modules/vite/bin/vite.js` (so `vitest/vitest.mjs` never matches);
- python or `celery`: `manage.py runserver`, or Celery as a program: the executable named
  `celery`, a path segment `/celery` or `/celery.exe` followed by whitespace or the end, or
  `-m celery`. A test file `test_celery_config.py` has no such segment.
Tests for Vitest, Playwright's preview of another checkout, a pytest path with "celery".

**D3. Unreadable processes (SCR-3).** Windows lists every process (`CommandLine` may be null);
the mapper keeps `cmd: null`. `matchStack` returns `{ kill, remove, unknown }`: a record whose pid
is alive with `cmd === null` and the recorded executable goes to `unknown` (record kept, not
killed); `ownedByPath` ignores `cmd === null`. `stop.mjs` prints "Could not check <pid> (<exe>):
its command line is not readable (started elevated?); left running." per unknown.

**D4. Direct signal without a group (SCR-4).** `runChild` computes `grouped = posix &&
(options.detached ?? true)`; `stop` sends `process.kill(-pid, signal)` when grouped, otherwise
`child.kill(signal)`; the forced kill uses `killTree(child.pid)` when grouped or on Windows, else
`child.kill('SIGKILL')`.

**D5. Redis runner exits (SCR-6, SCR-7).** `stop(code = 0)`; the wait failure calls `stop(1)`.
`session.on('error', (error) => { console.error(`Could not start the WSL keep-alive:
${error.message}`); stop(1) })` (a failed spawn emits `'error'` and no `'exit'` with a pid).

**D6. Small ones.** SCR-8: `url.hostname.replace(/^\[(.*)\]$/, '$1')`. SCR-9: sort install folders
by the number after `Python` (descending; non-matching names last, as before). SCR-10: `import {
root } from './env.mjs'` in the three scripts (`env.mjs` reads `.env` only in `loadEnv()`, so
`setup.mjs` can import it before `.env` exists).

## Risks / Trade-offs

- [A future runner launches Vite or Celery differently] → `stack.test.mjs` lists the shapes; the
  recorded runner still matches by record either way, only orphans rely on path matching.
- [Listing every Windows process returns more rows] → Same query without the filter; output
  size is bounded by the existing 64 MiB buffer.
