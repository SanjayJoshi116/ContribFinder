## Context

- **Keep-alive (P-1).** `scripts/redis.mjs` starts `wsl.exe -d <distro> -- sleep infinity`
  (detached, hidden console) and records it in `.run/`. On its `exit` it logs "WSL keep-alive
  session ended (code N); Redis may stop." and calls `process.exit(1)`. `concurrently` then
  stops every runner. On 2026-10-22 a keep-alive exited with `3221225786` (`0xC000013A`, the
  Windows Ctrl+C exit status) about 8 s after a start from Claude Code's shell. It did not happen
  again. The cause is unknown; the reaction (whole stack down) is the defect we can fix. `stop()`
  kills the keep-alive itself, so an intended stop also fires `exit`.
- **Line endings (P-2).** The repository has no `.gitattributes`. Every file in the index is
  already LF (`git ls-files --eol`: 598 `i/lf`, 35 `i/none`). On Windows with
  `core.autocrlf=true` the working copy is CRLF, and Prettier (default `endOfLine: "lf"`)
  reports every file. CI (Linux) checks out LF.
- **Flaky tests (P-3).** Two of 35 tests in `src/app/app.test.tsx` and
  `src/features/feedback/feedback.test.tsx` failed once during an 82 s run while other suites
  ran; the same files passed alone in 12 s. The names were not captured. `asyncUtilTimeout` is
  already 5 s and `testTimeout` 15 s (`vite.config.ts`, `src/test/setup.ts`).
- **`api:export` (P-4).** It runs `cd ../backend && uv run python manage.py spectacular ...`.
  Every other backend command goes through `scripts/uv.mjs` (`scripts/manage.mjs` for
  management commands).
- **Scripts lint (P-5).** Root `package.json` has only `concurrently`. ESLint and Prettier
  configs live in `apps/frontend` and cover only its files. CI runs `node --test
  "scripts/*.test.mjs"` in the `api-contract` job.
- **Snapshots (Q-10, Q-11).**
  - `RepositorySnapshot.Meta.indexes` is `(repository, -captured_at)`.
  - The newest-first order `("-captured_at", "-pk")` appears in three places:
    `repositories/queries.latest_snapshot`, `repositories/api.py:109`, and
    `services/repositories/analysis.py:317` (history trim).
  - Snapshots per repository are capped at `REPO_SNAPSHOT_HISTORY`.
- **Leftovers (Q-12).**
  - `_update_metadata` has 7 call sites in `services/github/sync.py` and 9 in
    `services/discovery/service.py`.
  - `tests/repo_fixtures.py` re-exports four builders from `e2e.builders`, and 16 test modules
    import them through it.

## Goals / Non-Goals

**Goals:**
- One bad keep-alive session does not take the stack down.
- A clean checkout on any OS passes every check CI runs.
- Each newest-snapshot read uses one index order, written once.

**Non-Goals:**
- Finding why the keep-alive exited. The runner now logs the code in hex, which is what the
  next occurrence needs.
- Storing activity fields on `Repository`, or a `DISTINCT ON` query. The capped history
  bounds the rows read; removing the sort is enough for now (see Risks).
- Linting the frontend or backend differently. Only `scripts/` gains checks.

## Decisions

**D1. Restart the keep-alive with a budget (P-1).** New pure helper in `scripts/restarts.mjs`:
`restartBudget({ max = 3, windowMs = 300_000 })` returns `{ allow(now) }`. `allow` drops
timestamps older than the window, refuses once `max` remain, and otherwise records `now`.
In `redis.mjs`:
- `startKeepAlive()` spawns and records the session. It keeps the record's file name and
  removes the old record when that session exits.
- `exit` handler:
  - if a stop is under way (a `stopping` flag set by `stop()`), do nothing;
  - else if the budget allows, log `WSL keep-alive session ended (code N, 0x…); starting a new
    one.` and start again;
  - else log `WSL keep-alive ended 4 times in 5 minutes; giving up.` and exit 1.
- *Alternative:* keep exiting, and only improve the message. Rejected: one stray console event
  kills Django, Vite and the workers for nothing; Redis itself (the service) is still running.

**D2. `.gitattributes` with `* text=auto eol=lf` (P-2).** Nothing to renormalize: the index
is already LF. Existing Windows checkouts keep CRLF working copies until they are rewritten.
The README tells developers to rewrite them once on a clean tree: `git ls-files -z | xargs -0
rm -f && git checkout -- .`. *As built:* `git checkout-index --force --all` skipped files whose
stat still looked clean, so it left CRLF in place.
Binary files are detected by `text=auto`. No `.cmd`/`.bat`/`.ps1` files exist, so nothing needs
`eol=crlf`.
- *Alternative:* Prettier `endOfLine: "auto"`. Rejected: it hides the mismatch only from
  Prettier. Other tools (ESLint `linebreak` rules, shell scripts in WSL) still see CRLF.

**D3. Flaky tests: reproduce first (P-3).**
- Run the two files 5 times with the backend test suite running at the same time, and
  `--reporter=verbose` to capture the failing names.
- Fix each failure at its cause. Typical causes: waiting on text that renders before the data,
  or counting requests before the refetch settles. Wait for the element or the request
  (`waitFor(() => expect(callsTo(...)).toHaveLength(n))`), never a longer global timeout.
- If 5 runs do not reproduce it, record the runs in the backlog row and leave it open.

**D4. `api:export` through `scripts/manage.mjs` (P-4).** The new command is
`node ../../scripts/manage.mjs spectacular --settings config.settings.test --format
openapi-json --validate --fail-on-warn --file ../frontend/src/api/openapi.json`.
`manage.mjs` runs in `apps/backend`, so the `--file` path is unchanged. CI (`setup-uv`, uv on
PATH) is unaffected.

**D5. Root lint and format for `scripts/` (P-5).**
- `.prettierrc.json` moves from `apps/frontend` to the repository root. Prettier looks for its
  config upwards, so the frontend uses the same file and there is one style. The frontend's
  `.prettierignore` stays where it is.
- Root `eslint.config.mjs`: `@eslint/js` recommended plus `globals.node`, for `scripts/**/*.mjs`
  only. The frontend keeps its own config, which ESLint finds first in `apps/frontend`.
- Root devDependencies use the frontend's current versions: `eslint`, `@eslint/js`, `globals`,
  `prettier`.
- New scripts: `lint:scripts` (`eslint scripts`) and `format:scripts` (`prettier --check
  scripts`).
- One `prettier --write scripts` reformats the existing files.
- CI: the `api-contract` job (it already runs the script tests) adds a root `npm ci`,
  `lint:scripts` and `format:scripts`. Its `cache-dependency-path` lists both lockfiles.

**D6. Index with the tie-break and one ordering constant (Q-10, Q-11).**
- `repositories/queries.py` gets `SNAPSHOT_NEWEST_FIRST = ("-captured_at", "-pk")`, used by
  `latest_snapshot`, `repositories/api.py` and the history trim in
  `services/repositories/analysis.py`.
- `RepositorySnapshot.Meta.indexes` becomes `(repository, -captured_at, -id)`, added by a new
  migration that replaces the old index.
- `Meta.ordering` stays as it is. Changing it would alter every default query's SQL for no gain.
- Check with `EXPLAIN` that the prefetch window now reads the index in order with no Sort node.
- *As built (EXPLAIN on the dev database, 336 snapshots):*
  - The single-repository reads, which are the candidates API subquery and the history trim,
    are now `Index Scan` + `Limit` on the new index, with no Sort, reading one row.
  - The multi-repository `latest_snapshot` prefetch filters `repository_id = ANY(...)`, so it
    still sorts its rows: Postgres uses an unordered bitmap scan there. That cost stays bounded
    by `REPO_SNAPSHOT_HISTORY` per repository, so Q-10 is only partly fixed. Stored activity
    stays `ideas.md` §16.

**D7. Remove the leftovers (Q-12).**
- `_update_metadata(**kw)` → `merge_metadata(self.job, {...})` at each call site, and both
  methods are deleted.
- Test modules import `add_candidate`, `fresh_repo`, `make_candidate_repo` and `make_issue`
  from `e2e.builders`, and the re-export and `__all__` leave `tests/repo_fixtures.py`.

## Risks / Trade-offs

- [A keep-alive that keeps dying is restarted silently] → Each restart is logged. After 3 in 5
  minutes the runner fails as before.
- [The prefetch still reads every snapshot of the prefetched repositories] → The index removes
  the sort, and `REPO_SNAPSHOT_HISTORY` bounds the rows per repository. Stored activity on
  `Repository` stays an idea (`ideas.md` §16) if profiling ever shows this matters.
- [Moving `.prettierrc.json` changes where the frontend's style lives] → Same options, one
  file. `npm run format:check` in `apps/frontend` is the check.
- [Existing CRLF working copies still fail format checks until refreshed] → README step,
  one command on a clean tree.

## Migration Plan

- One schema migration (index swap; online on PostgreSQL for this table size). Rollback
  reverses it.
- Developers on Windows rewrite their working files once after pulling, with no local changes
  (README command).
- `npm run setup` (or `npm ci` at the root) installs the new root devDependencies.
