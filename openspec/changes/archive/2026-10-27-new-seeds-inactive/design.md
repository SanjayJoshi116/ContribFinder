## Context

See proposal.md for why; the requirement is in `specs/recommendation-engine`.
- `0002_seed_v1_deterministic` and `0003_seed_v2_deterministic` (`recommendations/migrations/`)
  each carry their own activation and rollback logic, covered by `tests/test_seed_migrations.py`
  (rollback/re-apply matrix, operator choice, `test_real_migrations_round_trip`).
- Migrations hold frozen copies of their numbers (0003's comment: "a migration must not change
  when that module does later"); they use `apps.get_model`, never the live model.
- `services/ranking/activation.activate` is the one activation path (benchmark judge, audit
  `scoring_config_activated`, `via: "command"`). `config.validate(weights, params, stored=True)`
  validates stored configurations.
- Django's `MigrationLoader` skips modules in a migrations package whose name starts with `_`
  or `~`, so `recommendations/migrations/_seeding.py` can hold shared code without being a
  migration.

## Goals / Non-Goals

**Goals:**
- A later seed is a few lines: frozen numbers plus one helper call each way.
- The rule is enforced by a test, not only by review.

**Non-Goals:**
- Changing the v1 or v2 seed, or which configuration a fresh or upgraded database ends with.
- Adding a configuration (v3 waits for K-1).
- Activating from a migration under any condition, including an empty database (v2 already
  covers that; a later version never needs to).

## Decisions

**D1. Helper module `recommendations/migrations/_seeding.py`, frozen.**
- `store_inactive(apps, *, version, description, weights, params) -> None`: when `version` is
  stored, return (no field changes, activation untouched); otherwise create it with
  `is_active=False`. `remove_unused(apps, *, version) -> None`: delete the row only when it is
  inactive and has no recommendations; otherwise do nothing.
- Both take the historical `apps`, use `apps.get_model("recommendations", "ScoringConfig")` and
  read no settings or services, so a migration that calls them behaves the same later. The
  module docstring states it is frozen: changing behavior means a new function, never an edit,
  because applied migrations already depend on it.
- *Alternative:* copy the logic into each future migration. Rejected: the v2 seed shows how much
  rollback logic drifts; one tested function is safer than N copies.
- *Alternative:* put the helper in `services/ranking/`. Rejected: services change with the app,
  and a migration must not.

**D2. Reversal never re-activates and never deletes a version in use.**
- An inactive seed left activation alone, so its reversal does too: an active version (the
  operator activated it) stays stored and active, since deleting it would leave none active and
  re-activating a predecessor is an operator decision. A version with recommendations is
  `PROTECT`ed anyway.
- *Alternative:* fall back to the previous active configuration on reverse, as 0003 does.
  Rejected: that is the logic this change removes, and "previous" is not recorded.

**D3. Tests.**
- Helper tests in `tests/test_seed_migrations.py` with a test version (`test-seed-v9`): stored
  inactive while v2 or an operator choice is active; re-apply after operator activation changes
  nothing (values and activation); reverse deletes when inactive and unused; reverse keeps it
  when active or with recommendations, with exactly one active after each step.
- Guard on the migrated test database: active versions ⊆ {`v2-deterministic`} (the fixture
  database is fully migrated from empty), every stored configuration passes
  `config.validate(..., stored=True)`, and `ACTIVATING_SEEDS = {"v1-deterministic",
  "v2-deterministic"}` names the only seeds allowed to activate. A later seed that activates
  fails the guard.

## Risks / Trade-offs

- [A fresh install with a later seed still runs v2 until the operator activates] → Intended:
  activation must pass the benchmark rule; the README step says so.
- [The guard sees only migrations, not a future data command that activates] → Activation code
  outside migrations already goes through `activation.activate` (spec "Activating a
  configuration").
- [Someone edits `_seeding.py` later] → Docstring rule plus the helper tests; an edit that
  changes behavior fails them.

## Migration Plan

- No migration in this change. Deploy; nothing stored changes.
- Rollback: revert the release (no migration uses the helper yet).
