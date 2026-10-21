## Purpose

Defines how the local development stack, the one-time setup, the version-consistency check and
CI behave, so that running, stopping and checking ContribFinder never touches another project
and never lets a commit go unchecked.

## ADDED Requirements

### Requirement: Stopping the local stack stops only this repository
`npm run stop` SHALL stop the runners, workers, servers and helper processes that this
repository's local stack started, and SHALL NOT stop processes of any other project, even when
those run identically named scripts. A process SHALL be stopped only when it was recorded by
one of this repository's runners and still matches the recorded program, or when its command
line names this repository's path.

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
