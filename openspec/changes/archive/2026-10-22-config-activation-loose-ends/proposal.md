## Why

These are the loose ends left after 0.12.12 that don't change ranking, re-checked on
2026-10-22:
- **Activation has no guard.** Choosing the active scoring configuration is the most
  ranking-visible operator action, yet it is a bare admin checkbox action. It runs no
  benchmark check, records no audit entry and asks for no reason, even though the spec says a
  configuration replaces the active one only when it wins on the selection benchmark
  (`recommendation-evaluation`, "Replacing the active configuration"). Z-1 (0.12.12) now sends
  operators to that action to re-activate v2 after a rollback. `ideas.md` §15 proposes an
  explicit command.
- **P-3 (flaky frontend tests) has a cause.**
  - The dashboard loads `LanguageChart` (Recharts) lazily. Its first import in a test file
    evaluates synchronously for about 1 s, inside whichever test is running when it resolves.
  - Measured: `does not retry a 429` takes 1.2–1.3 s, and its 50 ms settle blocks the event
    loop for about 980 ms. With the module preloaded the test takes 250 ms.
  - On a cold, loaded run that cost grows and lands in a random test.
- **Helper modules exit 0 when run** (`ideas.md` §15). `node scripts/uv.mjs ...` does nothing
  and reports success, which once passed for a green mypy run.
- **Q-10 (prefetch sort) needs a decision, not code.**
  - On PostgreSQL 18, a `DISTINCT ON` rewrite of the newest-snapshot prefetch still plans an
    incremental sort, at 0.4 ms for 40 repositories. The cost is bounded by
    `REPO_SNAPSHOT_HISTORY`.
  - Accept it, with the evidence; stored activity stays an idea.

Batch 8 still waits for K-1.

## What Changes

- **`activate_scoring_config <version>` command, and one activation rule.**
  - Activation goes through one service (`services/ranking/activation.py`), from the command
    and from the admin action.
  - It refuses an unknown or invalid configuration.
  - It refuses a configuration that is not an improvement over the active one on the
    selection benchmark (the evaluation improvement rule). `--force --reason "<why>"` allows a
    deliberate exception such as a rollback.
  - It deactivates the previous configuration and activates the new one in one transaction, so
    exactly one stays active.
  - It records an audit event with both versions, the verdict and the reason.
  - Re-activating the configuration that is already active changes nothing and says so.
  - The admin "Activate" action applies the same rule without `--force`. A refused activation
    shows the failed metrics, and a forced one needs the command.
- **P-3 fix.** The frontend test setup preloads `LanguageChart`, so no test pays for the lazy
  import. P-3 is closed when the two named files pass 5 times under backend-suite load.
- **Helper modules refuse to run.** `child.mjs`, `env.mjs`, `stack.mjs`, `uv.mjs` and
  `restarts.mjs` print that they are libraries and exit 1 when started directly. A test covers
  each.
- **Q-10 closed as accepted** in `Bug_Backlog.md`, with the EXPLAIN evidence.
- **Docs.** 0.12.12's Z-1 note pointed at the admin action. Re-activating v2 over v1 is not a
  benchmark improvement on `benchmark-v1`, so the note now names `activate_scoring_config
  v2-deterministic --force --reason ...`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-evaluation`: new requirement "Activating a configuration". The operator
  activation path enforces the improvement rule on the selection benchmark, unless it is
  forced with a recorded reason, and is audited.
- `developer-tooling`: new requirement "Library scripts refuse to run as commands".

## Impact

- Backend:
  - new `services/ranking/activation.py`;
  - new `recommendations/management/commands/activate_scoring_config.py`;
  - `recommendations/admin.py` (the action calls the service);
  - `accounts/models.py`: new `AuditEvent.Action.SCORING_CONFIG_ACTIVATED`, a choices-only
    migration;
  - `services/audit.py`: new allowed metadata keys `config_version`, `previous_version`,
    `forced`, `failures`;
  - tests.
- Frontend: `src/test/setup.ts` (test-only).
- Scripts: `scripts/env.mjs` gets a `refuseRun(import.meta.url)` helper, called by the five
  library modules; `scripts/*.test.mjs`.
- API, UI, ranking: unchanged. Patch release 0.12.13.
- Docs: `Bug_Backlog.md` (P-3, Q-10), `ideas.md` §15 (activation command and loud helpers
  shipped), CLAUDE.md §6 (the new command next to `evaluate_ranking`) and §7, README ("Evaluating
  a ranking change"), CHANGELOG (including the 0.12.12 Z-1 wording), features.
