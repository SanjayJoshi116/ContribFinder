## 1. Activation service and audit (D1, D4)

- [x] 1.1 `accounts/models.py`: `AuditEvent.Action.SCORING_CONFIG_ACTIVATED`. Run
  `makemigrations --settings config.settings.test`; the result must be a choices-only
  `AlterField`.
- [x] 1.2 `services/audit.py`: add the allowed metadata keys `config_version`,
  `previous_version`, `forced`, `failures` and `via`. Leave `IDENTIFYING_METADATA_KEYS` as it
  is.
- [x] 1.3 `services/ranking/activation.py`:
  - `ActivationError` and `ActivationRefused(failures)`;
  - an `Activation` result (`version`, `previous`, `changed`, `forced`, `failures`);
  - `benchmark_judge(candidate, active)`, which evaluates both on `selection_dataset()` with the
    settings defaults and returns the `Verdict`;
  - `activate(version, *, force, reason, via, user=None, request=None, judge=benchmark_judge)`,
    with the steps in design D1. The transaction locks the configuration rows by pk.
- [x] 1.4 Tests (`tests/test_activation.py`), with an injected judge unless noted:
  - an improvement activates and audits `forced=False`;
  - a refusal raises with the failures and changes nothing;
  - force without a reason raises before the judge is called;
  - a forced activation audits the reason and the failures;
  - an unknown version and an invalid stored configuration are refused;
  - the already-active configuration returns `changed=False` with no audit event;
  - exactly one configuration is active afterwards;
  - one test with the real `benchmark_judge`: activating v1 over v2 is refused on
    `benchmark-v1` (pinned by `baselines.json`).

## 2. Command and admin (D2, D3)

- [x] 2.1 `recommendations/management/commands/activate_scoring_config.py`: a `version`
  positional argument plus `--force` and `--reason`. It prints the verdict and the result, and
  turns service errors into a `CommandError`.
- [x] 2.2 `recommendations/admin.py`: `activate` calls the service with `via="admin"`, the
  user and the request. A refusal is an error message with the failures and the command hint.
- [x] 2.3 Tests:
  - the command's success output and audit event;
  - the refusal (non-zero exit with the failures listed);
  - `--force` without `--reason`;
  - the already-active message;
  - the admin action refusing with the failures and changing nothing (admin client, injected
    judge via `monkeypatch`).

## 3. Frontend test timing (D5, P-3)

- [x] 3.1 `src/test/setup.ts`: `await import('@/features/profile/LanguageChart')` with a
  comment (the lazy import in `routes/AppShell.tsx`; preload any future lazy component too).
- [x] 3.2 `does not retry a 429` takes under 500 ms in 3 runs (it was about 1.2 s). Run
  `app.test.tsx` and `feedback.test.tsx` 5 times while the backend suite runs: no failure.
  Record the runs in P-3.

## 4. Loud library scripts (D6)

- [x] 4.1 `scripts/env.mjs`: `refuseRun(moduleUrl)`, and call it on `env.mjs` itself.
  `child.mjs`, `stack.mjs`, `uv.mjs` and `restarts.mjs` call `refuseRun(import.meta.url)`.
- [x] 4.2 `scripts/libraries.test.mjs`: each of the five, run with `node`, exits 1 with the
  library message on stderr. `npm run test:scripts`, `lint:scripts` and `format:scripts` pass.
- [x] 4.3 Manual: `npm run manage -- check` and `npm run check:version` still work.

## 5. Verification and housekeeping

- [x] 5.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest` (including
  `tests/test_privacy_coverage.py`, which must still pass). Frontend lint, format:check,
  typecheck, test, build. Root `test:scripts`, `lint:scripts`, `format:scripts`,
  `check:version`. No `npm run e2e`: nothing here touches browser flows or the e2e runner
  (CI still runs it).
- [x] 5.2 Manual: `npm run manage -- activate_scoring_config v1-deterministic` is refused with
  the metrics. Then `--force --reason "test"` activates v1, and re-activating v2 also needs
  `--force`. Restore v2 at the end and check the two audit events in the admin.
- [x] 5.3 `Bug_Backlog.md`: P-3 `fixed (config-activation-loose-ends)` with the cause, and
  Q-10 `accepted (bounded)` with the plan. Update the "Next" line.
- [x] 5.4 `ideas.md` §15: mark the loud helper modules and the activation command shipped
  (seeds still activate; storing them inactive stays open). Update the round 5 table.
- [x] 5.5 CLAUDE.md:
  - §6: `activate_scoring_config`, next to `evaluate_ranking`;
  - §4: `services/ranking/activation.py`;
  - §7: shipped entry, plus the 0.12.12 entry's Z-1 line (re-activate v2 through the command
    with `--force`).
  README "Evaluating a ranking change": activation goes through the command.
- [x] 5.6 Release housekeeping (CLAUDE.md §8), patch release 0.12.13:
  - `VERSION`, the package files and lockfiles;
  - `CHANGELOG.md` (and the 0.12.12 Z-1 line), `features.txt`, README status line.
