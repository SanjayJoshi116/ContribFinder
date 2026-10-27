## Why

Seed migrations still decide which scoring configuration is active: `0003_seed_v2_deterministic`
activates v2 over v1, and needed three rounds of fixes to stay correct on rollback and re-apply
(H-10, H-11, Z-1). Since v0.12.13 activation has its own path, `activate_scoring_config`
(benchmark-gated, `--force --reason`, audited), and since v0.12.18 it is the only path outside
migrations. A seed that activates its version skips the benchmark rule and the audit entry, and
every activating seed needs its own rollback logic. `ideas.md` §15 "New seeds stored inactive" is
the top "can ship now" idea. No ranking change: no current seed changes, and no new
configuration is added.

## What Changes

- Rule: every scoring configuration seed after `v2-deterministic` stores its version inactive
  and never changes which configuration is active; the operator activates it with
  `activate_scoring_config`. The `v1-deterministic` and `v2-deterministic` seeds keep their
  behavior (existing installs and a fresh database still end with v2 active).
- A shared, frozen seeding helper for later migrations: store a version inactive (no change when
  the version is already stored) and, in reverse, delete it only when it is inactive and produced
  no recommendations.
- A guard test: on a fully migrated database, only `v1-deterministic` or `v2-deterministic` can
  be active, and every other configuration a migration stored is inactive.
- README "Evaluating a ranking change": how to add a configuration (seed inactive → evaluate →
  activate).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-engine`: "Versioned scoring configuration" — seeds after `v2-deterministic`
  store their version inactive and leave activation alone; their reversal deletes only an
  inactive version without recommendations.

## Impact

- Backend: `recommendations/migrations/_seeding.py` (new helper; the leading underscore keeps
  Django's migration loader from treating it as a migration), `tests/test_seed_migrations.py`.
  No migration, no setting, no API change.
- Docs: README (adding a configuration), `ideas.md` §15 to "Shipped", CLAUDE.md §7 shipped
  entry, CHANGELOG, `features.txt`.
- Release: patch 0.12.28.
