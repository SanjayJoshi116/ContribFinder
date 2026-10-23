## Context

See proposal.md for why.
- **Activation today.** `ScoringConfigAdmin.activate` (`recommendations/admin.py`) deactivates
  every other configuration and activates the chosen one in one transaction. It runs no
  validation, no benchmark and no audit.
  - A partial unique constraint keeps at most one configuration active.
  - The freshness sweep regenerates every developer's recommendations under the new active
    configuration (`recommendation-engine`, "New configuration activated").
- **Evaluation pieces already exist** in `services/evaluation/runner.py`: `stored_config(version)`
  (validates with `stored=True`, raises `ConfigError`), `active_config()`,
  `evaluate(dataset, spec, min_score=, top_n=)` and `compare(baseline, candidates, tolerance)`.
  `dataset.selection_dataset()` picks the selection benchmark. `evaluate_ranking` defaults to
  `settings.RECOMMENDATION_MIN_SCORE` and `RECOMMENDATIONS_TOP_N`.
- **Audit.** `services/audit.record(action, outcome, user=, request=, metadata=)` allowlists
  metadata keys. `AuditEvent.Action` is a `TextChoices`.
- **P-3.** `routes/AppShell.tsx` loads `LanguageChart` with `lazy()`, the only lazy component.
  Vitest isolates modules per test file, so each file pays the Recharts import once, at
  whatever moment the dashboard first renders the chart. The measurements are in the proposal.
- **Library scripts.** `env.mjs` has `isMain(moduleUrl)`. `check-version.mjs` and
  `wait-port.mjs` are libraries with a CLI behind `isMain`. `child.mjs`, `env.mjs`,
  `stack.mjs`, `uv.mjs` and `restarts.mjs` are pure libraries.

## Goals / Non-Goals

**Goals:**
- One activation path that enforces the benchmark rule, leaves a trail and allows a deliberate
  override.
- Deterministic frontend test timing.
- Libraries that fail loudly.

**Non-Goals:**
- Changing the seeds to store new versions inactive (`ideas.md` §15 suggests it). No new seed
  is planned, and 0003 already leaves activation alone on a re-apply (Z-1).
- Running the holdout in the command. Which holdout is "current" is a judgment call made during
  a search, and seen holdouts must not accept a later search.
- An activation API or UI.
- Stored activity on `Repository` (Q-10's expensive option).

## Decisions

**D1. `services/ranking/activation.py`, used by the command and the admin.**
- `activate(version, *, force=False, reason="", via, user=None, request=None, judge=benchmark_judge)
  -> Activation`.
- Steps:
  1. `stored_config(version)`. A `ConfigError` or a missing version raises `ActivationError`.
  2. When it is already active, return `Activation(changed=False)` with no audit.
  3. `force` without a non-blank `reason` raises `ActivationError` before evaluating.
  4. `verdict = judge(candidate, active)`. When it is not an improvement and not forced, raise
     `ActivationRefused(failures)`.
  5. In `transaction.atomic()`: `select_for_update` on the configuration rows (lock order: by
     pk), deactivate the others, activate the candidate.
  6. `audit.record(SCORING_CONFIG_ACTIVATED, success, user=, request=, metadata={config_version,
     previous_version, forced, reason, failures, via})`.
- `benchmark_judge` loads `selection_dataset()`, evaluates both configurations with the
  settings defaults (as `evaluate_ranking` does without options) and returns
  `compare(active_report, [candidate_report])[0]`.
- *Why a judge parameter:* tests inject a fixed verdict, so they never depend on benchmark
  numbers. One test runs the real judge with v1 against v2, whose result `baselines.json`
  pins.
- With no active configuration (only possible by hand), the candidate is not compared;
  activation proceeds and records `previous_version` as empty.
- *Alternative:* put the gate in the admin only. Rejected: the command is the documented
  operator path, and the admin must not be a way around it.

**D2. The command `activate_scoring_config <version> [--force --reason TEXT]`.**
- It is a thin wrapper around the service. It prints the verdict (each failure on its own line)
  and the result, for example "`v1-deterministic` is active (forced); recommendations
  regenerate on the next freshness run."
- `ActivationError` and `ActivationRefused` become a `CommandError`, so the exit status is
  non-zero.
- `via="command"`, and `user` is None: management commands have no request user.

**D3. The admin action without force.**
- It calls `activate(..., via="admin", user=request.user, request=request)`.
- A refusal shows the failures as an error message, plus "use `npm run manage --
  activate_scoring_config <version> --force --reason ...` for a deliberate exception".
- The benchmark runs inside the request. That takes seconds on a dataset of this size, and the
  action is operator-only and rare.

**D4. Audit.**
- `AuditEvent.Action.SCORING_CONFIG_ACTIVATED = "scoring_config_activated"`, with a choices-only
  migration in `accounts`.
- New allowed metadata keys: `config_version`, `previous_version`, `forced`, `failures` (a list
  of strings) and `via`. `reason` is already allowed. None of them identifies a person, so
  `IDENTIFYING_METADATA_KEYS` is unchanged.
- The admin event has a user. Account deletion already anonymizes events through `SET_NULL`
  and `anonymize_user_entries`.

**D5. Preload the lazy chart in the test setup (P-3).**
- `src/test/setup.ts` ends with `await import('@/features/profile/LanguageChart')`. Every test
  file then pays the Recharts evaluation during setup, outside any test's timer.
- *Alternative:* mock `recharts`. Rejected: the chart's own tests need the real one.
- *Alternative:* remove `lazy()`. Rejected: lazy loading keeps Recharts out of the first
  bundle.
- The preload follows `AppShell`'s lazy import. A comment names it, so a new lazy component
  gets preloaded too.

**D6. `refuseRun(moduleUrl)` in `env.mjs` (loud libraries).**
- `export function refuseRun(moduleUrl)`: when `isMain(moduleUrl)` is true, it writes
  "`<relative path>` is a library used by other scripts; it is not a command." to stderr and
  calls `process.exit(1)`.
- `child.mjs`, `stack.mjs`, `uv.mjs` and `restarts.mjs` import it and call
  `refuseRun(import.meta.url)` at module end. `env.mjs` calls it on itself after the
  definition.
- `restarts.mjs` is pure today. Importing `env.mjs` adds no side effect (it only defines
  functions and constants).
- Tests (`scripts/libraries.test.mjs`): spawn `node <lib>` for each of the five, and expect
  status 1 and the message. The existing tests already import each module, which covers the
  import path.

**D7. Q-10 accepted.**
- On PostgreSQL 18 with seq and bitmap scans disabled, `DISTINCT ON (repository_id)` ordered
  by `SNAPSHOT_NEWEST_FIRST` plans an index scan on the `repository_id` index plus an
  incremental sort: 0.4 ms for 40 repositories and 336 snapshots.
- The current window prefetch is also bounded by `REPO_SNAPSHOT_HISTORY`, so no code change.
  The status becomes `accepted (bounded)`, with the plan recorded.

## Risks / Trade-offs

- [An operator needs a legitimate rollback quickly] → `--force --reason` is one command, and
  the reason is audited.
- [The benchmark can change between choosing and activating a configuration] → The command
  evaluates at activation time, which is the point: it records what was true then.
- [The admin request runs the benchmark] → It is acceptable at this dataset size. If it grows,
  the admin can drop the action and point to the command.
- [Preloading lengthens each test file's setup by about 1 s] → The total stays the same; it
  only moves out of the tests.

## Migration Plan

- One choices-only migration (`accounts`), with no data change. Rollback reverses it.
- No behavior change for users. Operators use the command, or the admin as before for
  improvements.
