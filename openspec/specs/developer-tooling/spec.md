# developer-tooling Specification

## Purpose

Defines how the local development stack, the one-time setup, the version-consistency check and
CI behave, so that running, stopping and checking ContribFinder never touches another project
and never lets a commit go unchecked.
## Requirements
### Requirement: Stopping the local stack stops only this repository
`npm run stop` SHALL stop the runners, workers, servers and helper processes that this
repository's local stack started, and SHALL NOT stop processes of any other project, even when
those run identically named scripts. A process SHALL be stopped only when it was recorded by
one of this repository's runners and still matches the recorded program, or when it is one of the stack's own programs (Django's
development server, a Celery worker or beat, the Vite dev server) and its command line names this
repository's path as a whole folder (another folder whose name starts with this one's is not this
repository). A test runner, editor or other program SHALL NOT be stopped because its command line
mentions the stack or the path. A recorded process that is alive but whose command line cannot be
read (for example started from an elevated console) SHALL be left running, its record kept, and
`npm run stop` SHALL say so.

#### Scenario: Another checkout keeps running
- **WHEN** two checkouts of ContribFinder (or another project with a `scripts/start.mjs`) run
  their stacks and `npm run stop` runs in one of them
- **THEN** only that checkout's processes end; the other stack keeps running

#### Scenario: Recorded process id reused
- **WHEN** a recorded runner has exited and the operating system has given its process id to an
  unrelated program
- **THEN** `npm run stop` leaves that program running and discards the stale record

#### Scenario: Redis keep-alive stopped
- **WHEN** `npm run stop` runs while the local stack keeps WSL awake for Redis
- **THEN** the keep-alive process ends too

#### Scenario: Sibling checkout with a longer name
- **WHEN** `npm run stop` runs in `G:\Projects\ContribFinder` while a stack runs from `G:\Projects\ContribFinder-v2`
- **THEN** the `ContribFinder-v2` processes keep running

#### Scenario: Test runners keep running
- **WHEN** `npm run stop` runs while Vitest runs in this repository's frontend and pytest runs a test file whose name contains "celery"
- **THEN** both keep running

#### Scenario: Process started elevated
- **WHEN** a recorded runner was started from an elevated console and `npm run stop` runs from a normal one
- **THEN** the runner is left running, its record is kept, and the command reports that it could not be checked

### Requirement: Closing the console stops the stack
When the console that runs the local stack closes (or the stack's parent process disappears),
every runner SHALL stop its children, including the WSL keep-alive, so nothing keeps running in
the background. A runner whose child already exited, or whose program cannot be started, SHALL
end with a readable message rather than an uncaught exception.

#### Scenario: Console window closed
- **WHEN** the user closes the terminal window that runs `npm start`
- **THEN** Django, Vite, the Celery worker and beat, and the WSL keep-alive all end

#### Scenario: Missing program
- **WHEN** a runner is configured with a program path that does not exist (for example a wrong
  `UV_BIN`)
- **THEN** it prints which program could not be started and exits with a failure status

### Requirement: Port waits keep their deadline
Waiting for a service port SHALL give up no later than shortly after its stated deadline, also
when the host silently drops connection attempts.

#### Scenario: Unreachable Redis host
- **WHEN** the stack waits 10 seconds for a Redis host that drops packets
- **THEN** the wait fails after about 10 seconds with a message naming the host and port, not
  after the operating system's connection timeout

### Requirement: One scheduler state per checkout
The Celery beat scheduler of each checkout SHALL keep its schedule state in a file of its own, so
two checkouts or worktrees on one machine never share or overwrite it.

#### Scenario: Two checkouts schedule independently
- **WHEN** two checkouts run `npm start` on the same machine
- **THEN** each beat uses a different schedule file

### Requirement: Setup reproduces CI's installs
`npm run setup` SHALL install the root and frontend dependencies exactly as recorded in their
lockfiles, as CI does, and SHALL NOT modify any lockfile.

#### Scenario: Clean working tree after setup
- **WHEN** a developer runs `npm run setup` in a clean checkout
- **THEN** no lockfile shows as modified afterwards

### Requirement: Version consistency covers lockfiles completely
The version check SHALL fail when any versioned file disagrees with `VERSION`, including both
the top-level version and the root package entry (`packages[""].version`) of each npm lockfile.

#### Scenario: Half-updated lockfile
- **WHEN** `package-lock.json` has the new top-level version but its root package entry still
  has the old one
- **THEN** `npm run check:version` fails and names the lockfile entry

### Requirement: Every commit on main is checked
CI SHALL run for every push to `main` to completion; a newer run SHALL cancel an older one only
for the same pull request.

#### Scenario: Two quick pushes to main
- **WHEN** two commits are pushed to `main` a minute apart
- **THEN** both CI runs complete

#### Scenario: New push to a pull request
- **WHEN** a pull request receives a new push while its previous run is still in progress
- **THEN** the previous run is cancelled

### Requirement: Local Redis stays reachable while the stack runs
On Windows, the Redis runner SHALL keep the WSL distro that runs Redis awake for as long as the stack runs. When the session that keeps it awake ends while the stack is running, the runner SHALL log the exit code and start a new one. After 3 such restarts within 5 minutes, the runner SHALL fail with a readable message instead of restarting again. Stopping the stack (Ctrl+C, `npm run stop`, closing the console) SHALL NOT start a new session. When Redis does not become reachable at start, or a keep-alive session cannot be started, the runner SHALL exit with a failure status and a readable message, so the rest of the stack stops too. A local `REDIS_URL` with an IPv6 host (`redis://[::1]:6379/1`) SHALL be treated as local.

#### Scenario: Keep-alive ends unexpectedly
- **WHEN** the WSL keep-alive session exits while `npm start` is running
- **THEN** the Redis runner logs the exit code, starts a new keep-alive, and the rest of the stack keeps running

#### Scenario: Keep-alive keeps failing
- **WHEN** the keep-alive session has ended 3 times within 5 minutes and ends again
- **THEN** the Redis runner exits with a failure status and a message naming the repeated exits

#### Scenario: Intended stop
- **WHEN** the stack is stopped with Ctrl+C or `npm run stop`
- **THEN** no new keep-alive session is started

#### Scenario: Redis never comes up
- **WHEN** `npm start` runs and Redis does not answer within the wait
- **THEN** the Redis runner exits with a failure status and the other runners stop

#### Scenario: Keep-alive cannot start
- **WHEN** starting the WSL keep-alive session fails
- **THEN** the Redis runner logs a readable message and exits with a failure status, without a stack trace

### Requirement: Format and lint checks pass on every platform
The repository SHALL check out text files with LF line endings on every platform, so a clean checkout passes the format checks on Windows as well as in CI. The runner scripts (`scripts/*.mjs`) SHALL be covered by a lint and a format check that CI runs.

#### Scenario: Clean Windows checkout
- **WHEN** the repository is cloned on Windows with Git's default line-ending settings and `npm run format:check` runs in `apps/frontend`
- **THEN** it passes

#### Scenario: Badly formatted runner script
- **WHEN** a change to a file in `scripts/` breaks the shared formatting or lint rules
- **THEN** CI fails on the scripts' lint or format step

### Requirement: Backend commands find uv without PATH
Every npm command that runs backend code (`npm start` and its runners, `npm run manage`, `npm run api:sync`) SHALL find `uv` the same way, without requiring it on PATH. Among Python installs that each provide `uv`, the newest Python version SHALL be tried first.

#### Scenario: Schema export without uv on PATH
- **WHEN** `uv` is installed but not on PATH, and `npm run api:sync` runs in `apps/frontend`
- **THEN** the OpenAPI schema and the generated types are written as with `uv` on PATH

#### Scenario: Several Python installs
- **WHEN** `uv` is installed for both Python 3.9 and Python 3.13 and not on PATH
- **THEN** the Python 3.13 one is used

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

### Requirement: Dependencies are audited for known vulnerabilities
CI SHALL audit every locked dependency set (the backend's Python lockfile, the frontend's npm
lockfile and the runners' npm lockfile) against public vulnerability advisories. The audit SHALL
use exactly the locked versions, never a fresh resolution. A Python dependency with any known
vulnerability, or an npm dependency with a high or critical advisory, SHALL fail CI. The audit
SHALL run on every commit CI checks and also on a weekly schedule and on demand, so an advisory
published after the last commit is still reported. An advisory that cannot be fixed yet SHALL be
accepted only by an explicit entry in the repository naming the advisory, the reason and the
date; no audit SHALL be skipped or allowed to fail silently.

#### Scenario: Vulnerable locked dependency
- **WHEN** a commit's backend lockfile pins a package version with a published advisory
- **THEN** the CI run for that commit fails and names the package and the advisory

#### Scenario: Advisory published later
- **WHEN** an advisory is published for a locked npm dependency at high severity after the last commit to `main`
- **THEN** the next weekly run fails without any new commit

#### Scenario: Low-severity npm advisory
- **WHEN** an npm dependency has only a low or moderate advisory
- **THEN** the audit reports it and CI does not fail

#### Scenario: Accepted advisory
- **WHEN** an advisory has no fixed version and the repository records it as accepted with a reason and a date
- **THEN** the audit passes and the accepted advisory stays visible in the repository

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

### Requirement: Docker development mode stays local and current
`docker compose up` SHALL publish the backend and the frontend only on the host's loopback
interface. The Redis container SHALL NOT be published on the host, so it never takes the port of
the WSL Redis that `npm start` uses, and the Postgres container SHALL stay on host port 5433. The
settings module SHALL come from `.env`, not from the shell that runs compose. Frontend edits on a
Windows host SHALL reach Vite in the container (polling when the compose file asks for it). The
README SHALL say how to rebuild so the frontend container uses newly added dependencies. The
Postgres credentials SHALL be defined once in the compose file.

`.env.example` SHALL list every setting the backend reads from the environment (except settings
read only by the test configuration), each with its default or as required. A setting the
shipped settings modules ignore SHALL NOT be listed. `DJANGO_DEBUG` SHALL apply to the
development settings (default on) and SHALL be ignored by production. The root `package.json`
SHALL offer a formatting command that writes besides the one that checks, and SHALL state the
minimum Node version its runners need.

#### Scenario: Backend not reachable from the network
- **WHEN** `docker compose up` runs on a laptop on a shared network
- **THEN** port 8000 and 5173 answer on `127.0.0.1` only

#### Scenario: Docker and the local stack on one machine
- **WHEN** the WSL Redis from `npm start` is running and the user runs `docker compose up`
- **THEN** compose starts without a port conflict, and `npm start` keeps using the WSL Redis

#### Scenario: Settings module exported in the shell
- **WHEN** the shell has `DJANGO_SETTINGS_MODULE=config.settings.production` exported and the user runs `docker compose up`
- **THEN** the containers use the settings module from `.env`

#### Scenario: Debug off in development
- **WHEN** `.env` sets `DJANGO_DEBUG=false` with the development settings
- **THEN** Django runs without debug pages

#### Scenario: Template covers the settings
- **WHEN** a setting read by `config/settings/base.py` or `production.py` is not in `.env.example`
- **THEN** a test fails naming it

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
