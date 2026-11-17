## Context

`INSTALLED_APPS` with migrations: Django contrib (`admin`, `auth`, `contenttypes`, `sessions`)
and the nine project apps; the third-party apps (`rest_framework`, `django_filters`,
`corsheaders`, `drf_spectacular`) have none. Seven project migrations hold `RunPython`; all
already have a reverse (`RunPython.noop`, or `unseed` for the scoring seeds). CI already runs
`makemigrations --check`, so model/migration drift is covered; this change covers reversibility.

`tests/test_rank_constraint.py` already drives `MigrationExecutor` inside a
`django_db(transaction=True)` test; the new test follows that pattern.

## Goals / Non-Goals

**Goals:**
- One test: full unapply to zero, full reapply, schema compared, seeds checked.
- A clear failure naming the irreversible migration.

**Non-Goals:**
- Stepping through each migration one at a time (N round trips; too slow for little gain).
- Checking data-preserving behaviour of reverses with stored rows: reverses of data repairs are
  `noop` by design, and the seeds already have their own data tests.
- Squashing migrations or adding a pytest marker to skip slow tests.

## Decisions

- **Targets from the loader graph, not a hand list.** Start nodes are
  `executor.loader.graph.leaf_nodes()`; zero targets are `(app, None)` for every app label in
  `executor.loader.migrated_apps`. A new app is covered automatically. Alternative (hard-coded
  app list) rots silently.
- **Unapply everything, contrib included.** `auth`/`admin` depend on `accounts.User`
  (`AUTH_USER_MODEL`), so the project apps cannot reach zero alone; Django's own migrations are
  reversible. If one ever is not, exclude it explicitly with a comment rather than narrowing the
  target list.
- **Schema snapshot via introspection.** Before and after, collect per table
  `connection.introspection.get_table_list`, column names and types (`get_table_description`)
  and constraint/index names with their columns (`get_constraints`), excluding
  `django_migrations` rows. Compare as plain dicts so pytest shows the diff. Alternative
  (`pg_dump --schema-only`) needs the binary on PATH and diffs noisily.
- **Readable failure for irreversible operations.** Django raises `IrreversibleError` naming the
  operation and migration; let it propagate (no catch), so the scenario "names the app and
  migration" holds without extra code.
- **Rebuild the graph before going forward** (`executor.loader.build_graph()`), as the rank test
  does, so the executor sees the unapplied state.
- **Seeds:** after reapply, `ScoringConfig` holds the seeded versions and `active_configs()`
  has exactly one entry.

## Risks / Trade-offs

- [Transactional test flushes tables afterwards, removing seeded configs for later tests] →
  pytest-django runs transactional tests after the others, same as the existing transactional
  tests; the round trip also reseeds before the flush. Verify the full suite passes (the suite
  uses default order, no random-order plugin).
- [Slow: ~40 migrations twice] → measured during implementation; acceptable if a few seconds.
  If it exceeds ~30 s, revisit (record in the release entry) rather than adding a skip marker.
- [Contrib migration irreversible in a future Django] → explicit exclusion with a comment, test
  still covers project apps above it.

## Migration Plan

Test-only change; nothing to deploy or roll back.
