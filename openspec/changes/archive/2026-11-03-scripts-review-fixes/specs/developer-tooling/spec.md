## MODIFIED Requirements

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


### Requirement: Backend commands find uv without PATH
Every npm command that runs backend code (`npm start` and its runners, `npm run manage`, `npm run api:sync`) SHALL find `uv` the same way, without requiring it on PATH. Among Python installs that each provide `uv`, the newest Python version SHALL be tried first.

#### Scenario: Schema export without uv on PATH
- **WHEN** `uv` is installed but not on PATH, and `npm run api:sync` runs in `apps/frontend`
- **THEN** the OpenAPI schema and the generated types are written as with `uv` on PATH

#### Scenario: Several Python installs
- **WHEN** `uv` is installed for both Python 3.9 and Python 3.13 and not on PATH
- **THEN** the Python 3.13 one is used

