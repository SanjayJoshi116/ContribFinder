## ADDED Requirements

### Requirement: Local Redis stays reachable while the stack runs
On Windows, the Redis runner SHALL keep the WSL distro that runs Redis awake for as long as the stack runs. When the session that keeps it awake ends while the stack is running, the runner SHALL log the exit code and start a new one. After 3 such restarts within 5 minutes, the runner SHALL fail with a readable message instead of restarting again. Stopping the stack (Ctrl+C, `npm run stop`, closing the console) SHALL NOT start a new session.

#### Scenario: Keep-alive ends unexpectedly
- **WHEN** the WSL keep-alive session exits while `npm start` is running
- **THEN** the Redis runner logs the exit code, starts a new keep-alive, and the rest of the stack keeps running

#### Scenario: Keep-alive keeps failing
- **WHEN** the keep-alive session has ended 3 times within 5 minutes and ends again
- **THEN** the Redis runner exits with a failure status and a message naming the repeated exits

#### Scenario: Intended stop
- **WHEN** the stack is stopped with Ctrl+C or `npm run stop`
- **THEN** no new keep-alive session is started

### Requirement: Format and lint checks pass on every platform
The repository SHALL check out text files with LF line endings on every platform, so a clean checkout passes the format checks on Windows as well as in CI. The runner scripts (`scripts/*.mjs`) SHALL be covered by a lint and a format check that CI runs.

#### Scenario: Clean Windows checkout
- **WHEN** the repository is cloned on Windows with Git's default line-ending settings and `npm run format:check` runs in `apps/frontend`
- **THEN** it passes

#### Scenario: Badly formatted runner script
- **WHEN** a change to a file in `scripts/` breaks the shared formatting or lint rules
- **THEN** CI fails on the scripts' lint or format step

### Requirement: Backend commands find uv without PATH
Every npm command that runs backend code (`npm start` and its runners, `npm run manage`, `npm run api:sync`) SHALL find `uv` the same way, without requiring it on PATH.

#### Scenario: Schema export without uv on PATH
- **WHEN** `uv` is installed but not on PATH, and `npm run api:sync` runs in `apps/frontend`
- **THEN** the OpenAPI schema and the generated types are written as with `uv` on PATH
