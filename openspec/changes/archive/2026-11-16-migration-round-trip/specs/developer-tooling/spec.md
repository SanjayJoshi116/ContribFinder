## ADDED Requirements

### Requirement: Database migrations reverse and reapply cleanly

The backend test suite SHALL migrate every installed app back to before its first migration and
forward to its latest migration again. The round trip MUST succeed, the database schema after it
MUST match the schema before it, and the seeded scoring configurations MUST be present again with
exactly one active. The check SHALL run as part of the normal backend tests in CI.

#### Scenario: All migrations are reversible

- **WHEN** the backend tests run on a database at the latest migrations
- **THEN** every app is unapplied to before its first migration and reapplied without error

#### Scenario: Irreversible migration

- **WHEN** a migration contains an operation without a reverse
- **THEN** the backend tests fail and the failure names the app and migration

#### Scenario: Reverse leaves a database object behind

- **WHEN** a migration's reverse does not remove a table, column, constraint or index its forward
  created
- **THEN** the backend tests fail because the schema after the round trip differs from before

#### Scenario: Seed data after the round trip

- **WHEN** the round trip completes
- **THEN** the seeded scoring configurations exist again and exactly one of them is active
