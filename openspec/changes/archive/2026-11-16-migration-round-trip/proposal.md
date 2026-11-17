## Why

Only the scoring-config seeds (`tests/test_seed_migrations.py`) and the rank repair
(`tests/test_rank_constraint.py`) are tested in reverse. Nothing checks that every migration can
be unapplied and applied again, so the next irreversible operation, a `RunPython` without a
reverse, or a reverse that leaves a stray table, column, constraint or index would show up only
when someone rolls back a deploy. Now that the repository is public and outside contributors add
migrations, CI should catch this (ideas.md §4, "A generic data-migration round trip").

## What Changes

- One backend test migrates every installed app back to before its first migration, then forward
  to the latest migrations again, on the test database.
- After the round trip the database schema (tables, columns, constraints, indexes) must match the
  schema before it, and the seeded scoring configs must be back with exactly one active.
- The test runs in the normal `uv run pytest` suite (and so in CI). It is slower than most tests;
  no new marker or opt-out.
- A migration that cannot be reversed fails the test with the app and migration named.
- No runtime, API, ranking or data change. Patch release.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `developer-tooling`: adds a requirement that every database migration reverses and reapplies
  cleanly, checked in CI.

## Impact

- New test `apps/backend/tests/test_migration_round_trip.py`.
- CI backend job runs a few seconds longer.
- Future migrations must give every `RunPython`/`RunSQL` a reverse (`noop` where nothing needs
  undoing). CONTRIBUTING.md gains one line on this; CLAUDE.md §7 gains the durable rule.
- No change to models, migrations, settings, API or frontend.
