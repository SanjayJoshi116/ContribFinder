## 1. Helper (D1, D2)

- [x] 1.1 `recommendations/migrations/_seeding.py`: `store_inactive(apps, *, version,
  description, weights, params)` and `remove_unused(apps, *, version)` on the historical
  `ScoringConfig`; module docstring: frozen, change by adding a function, never by editing.
- [x] 1.2 Confirm the loader ignores it: `makemigrations --check --dry-run --settings
  config.settings.test` reports no changes and `showmigrations recommendations` lists no
  `_seeding`.

## 2. Tests (D3)

- [x] 2.1 `tests/test_seed_migrations.py`: the spec scenarios "Later seed stored inactive"
  (v2 active, and an operator choice active), "Later seed re-applied after the operator
  activated it" (values and activation unchanged), "Later seed reversed", "Later seed reversed
  while in use" (active; with recommendations), exactly one active after each step.
- [x] 2.2 Guard "Fully migrated database": only `v2-deterministic` active, every stored
  configuration valid under `config.validate(..., stored=True)`, `ACTIVATING_SEEDS` documented in
  the test.

## 3. Docs and release

- [x] 3.1 README "Evaluating a ranking change": adding a configuration (new migration with frozen
  numbers calling `_seeding.store_inactive` / `remove_unused`; `evaluate_ranking`; holdout;
  `activate_scoring_config`).
- [x] 3.2 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; `git diff --exit-code
  apps/backend/evaluation/baselines.json`. No frontend or e2e change.
- [x] 3.3 `ideas.md` §15 item to "Shipped"; CLAUDE.md §7 shipped entry (K-1 carry-over
  unchanged) and the Ideas paragraph; `features.txt`.
- [x] 3.4 Release housekeeping (CLAUDE.md §8): patch 0.12.28; `CHANGELOG.md`, README status line,
  lockfiles, `check:version`.
