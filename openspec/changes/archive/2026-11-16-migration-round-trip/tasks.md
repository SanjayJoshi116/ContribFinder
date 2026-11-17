## 1. Round-trip test

- [x] 1.1 Add `apps/backend/tests/test_migration_round_trip.py`: `django_db(transaction=True)`,
  `MigrationExecutor`, leaf nodes as the forward target, `(app, None)` for every migrated app
  as the zero target, `build_graph()` between the two
- [x] 1.2 Add a schema snapshot helper (tables, columns with types, constraints and indexes with
  their columns, via `connection.introspection`) and assert before == after
- [x] 1.3 Assert the seeded scoring configs exist again and exactly one is active
- [x] 1.4 Prove the test bites: temporarily drop a reverse (`RunPython(f)` without `noop`) and a
  `RunSQL` reverse in a scratch migration, see both fail with the migration named; revert
- [x] 1.5 Time the test; note the duration in the release entry

## 2. Checks

- [x] 2.1 `uv run pytest` (full suite, the transactional flush must not break later tests)
- [x] 2.2 `uv run ruff check . && uv run ruff format --check .` and `uv run mypy .`

## 3. Docs and release

- [x] 3.1 CONTRIBUTING.md: every `RunPython`/`RunSQL` needs a reverse (`noop` when nothing to
  undo); the round-trip test checks it
- [x] 3.2 ideas.md: remove "A generic data-migration round trip" and its matrix entry
- [x] 3.3 CLAUDE.md §7 durable rule (Backend conventions) and next items; CLAUDE_HISTORY.md entry
- [x] 3.4 Release housekeeping (CLAUDE.md §8): patch bump to 0.12.78, CHANGELOG, features.txt if
  applicable, README version line, `npm run check:version`
