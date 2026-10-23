## ADDED Requirements

### Requirement: Library scripts refuse to run as commands
A script under `scripts/` that only provides functions to other scripts SHALL, when started
directly with `node`, print that it is a library (naming the commands that use it is not
required) and exit with a non-zero status, without doing anything else. Importing it from another
script SHALL be unaffected.

#### Scenario: Library started by mistake
- **WHEN** a developer runs `node scripts/uv.mjs run mypy .`
- **THEN** it prints that `scripts/uv.mjs` is a library and exits with status 1, and no check runs

#### Scenario: Library imported
- **WHEN** `npm run manage -- check` imports `scripts/uv.mjs`
- **THEN** the command runs as before
