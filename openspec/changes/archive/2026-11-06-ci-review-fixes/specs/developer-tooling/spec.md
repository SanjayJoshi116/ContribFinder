## ADDED Requirements

### Requirement: CI installs the committed locks
CI SHALL install and run every dependency exactly as the committed lockfiles record them. A change
to a dependency list without the matching lockfile update SHALL fail CI instead of being resolved
on the fly. Tools that CI runs to generate committed files SHALL come from a lockfile too, never
from an unlocked download.

#### Scenario: Dependency added without locking
- **WHEN** a pull request adds a package to `apps/backend/pyproject.toml` without running `uv lock`
- **THEN** the backend job fails

#### Scenario: Generated API types
- **WHEN** CI regenerates `src/api/schema.d.ts`
- **THEN** it uses the generator version locked in `apps/frontend/tools/api-types/package-lock.json`

### Requirement: CI runs pinned third-party code without a stored token
Every third-party action a workflow uses SHALL be pinned to a full commit, with the version it
stands for noted next to it, and an automated update SHALL propose newer pins. No checkout SHALL
leave the job's token in the repository's git configuration.

#### Scenario: Action tag moved
- **WHEN** the owner of a used action moves its `v4` tag to another commit
- **THEN** CI keeps running the pinned commit until a pin update is merged

#### Scenario: Install script reads git config
- **WHEN** a dependency's install script reads `.git/config` during `npm ci`
- **THEN** it finds no token

### Requirement: Runner tests run on Windows and Linux
CI SHALL run the runner script tests (`npm run test:scripts`) on Windows as well as on Linux, so
the Windows-only paths of the runners are exercised.

#### Scenario: Windows-only branch broken
- **WHEN** a change breaks a runner test that only runs on Windows
- **THEN** CI fails

### Requirement: Browser test reports survive a timeout
When the browser tests fail or run out of time, CI SHALL keep the Playwright report and traces as
a downloadable artifact.

#### Scenario: Hung browser test
- **WHEN** a browser test hangs until the step's time limit
- **THEN** the run is marked failed and its report and traces are uploaded
