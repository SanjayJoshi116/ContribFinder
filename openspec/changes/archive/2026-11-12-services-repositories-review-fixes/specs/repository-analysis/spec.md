## MODIFIED Requirements

### Requirement: Repository data collection
For each candidate repository the system SHALL collect and store:
- metadata: owner, name, description, URL, default branch, stars, forks, open issues, primary language, license, creation, update and push dates, archived and fork flags;
- languages (bytes) and topics;
- the README;
- whether it has CONTRIBUTING documentation, a code of conduct, issue templates and a pull request template;
- whether it has a label that the issue label normalization (`issue-analysis` "Label normalization") maps to `good first issue`, and one it maps to `help wanted`;
- root dependency manifests, parsed into dependency names the same way as for the developer's own repositories;
- setup facts: whether CI configuration, tests, a dev environment configuration and a Docker Compose file were found;
- activity signals (see `repository-activity`);
- its open issues (see `issue-ingestion`).

Repository data SHALL be stored once and shared by every developer whose pool contains the repository. A repository whose data is still fresh SHALL NOT be fetched again for another developer's discovery.

Setup facts SHALL be detected from the repository's root entries and, when the root has a `.github` directory, the entries of `.github/workflows`, and SHALL be refreshed together with the dependency manifests, from the same root listing:
- CI: a workflow file (`.yml` or `.yaml`) in `.github/workflows`, or a root CI configuration of another service (for example `.gitlab-ci.yml`, `.travis.yml`, a `.circleci` directory, `azure-pipelines.yml`, `Jenkinsfile`);
- tests: a root test directory (for example `tests`, `test`, `spec`, `__tests__`) or a root test-runner configuration (for example `pytest.ini`, `tox.ini`, `jest.config.*`, `vitest.config.*`, `phpunit.xml`);
- dev environment: a `.devcontainer` directory, a `.devcontainer.json` file or a `.gitpod.yml` file;
- Docker Compose: `docker-compose.yml`, `docker-compose.yaml`, `compose.yml` or `compose.yaml`.

A fact not found SHALL be stored as not found, which means only that nothing matched at those locations; a repository not yet analyzed for them SHALL have them unknown. Setup facts SHALL NOT be used by any scoring signal, reason, filter or evaluation dataset.

#### Scenario: Candidate analyzed
- **WHEN** a newly discovered candidate is analyzed
- **THEN** its metadata, languages, topics, README, community files, labels, dependencies, setup facts, activity snapshot and open issues are stored

#### Scenario: Shared analysis
- **WHEN** two developers' discovery runs both find `encode/httpx` and its data is fresh after the first run
- **THEN** the second run makes no request for `encode/httpx` beyond its search result

#### Scenario: Missing optional files
- **WHEN** a repository has no README, no CONTRIBUTING file, no labels and no open issues
- **THEN** it is analyzed successfully and records that each of these is absent

#### Scenario: Entry labels with a scope or an alias
- **WHEN** a repository's labels are `type: good first issue` and `contributions welcome`, and issue analysis maps them to `good first issue` and `help wanted`
- **THEN** the repository is stored as having a `good first issue` and a `help wanted` label

#### Scenario: Setup facts found
- **WHEN** a repository's root holds `.github` (with `ci.yml` in `.github/workflows`), `tests/`, `.devcontainer/` and `docker-compose.yml`
- **THEN** CI, tests, dev environment and Docker Compose are all stored as found

#### Scenario: Nothing found
- **WHEN** a repository's root holds only `README.md` and `main.go`
- **THEN** its four setup facts are stored as not found, no request is made for `.github/workflows`, and the analysis succeeds

#### Scenario: Empty workflows directory
- **WHEN** a repository's root holds a `.github` directory whose `workflows` directory is missing or holds no `.yml` or `.yaml` file
- **THEN** CI is stored as not found, unless a root CI configuration of another service was found

#### Scenario: Analyzed before setup facts existed
- **WHEN** a repository's dependencies were last fetched before setup facts were collected
- **THEN** its setup facts are unknown until its dependencies are refreshed

#### Scenario: Setup facts never change ranking
- **WHEN** two otherwise identical candidates differ only in their setup facts
- **THEN** they receive the same score, reasons and match label

## ADDED Requirements

### Requirement: Identity confirmed before a refresh without metadata
A refresh that does not fetch a repository's metadata SHALL first look the repository up by its stored name and SHALL continue under that name only when GitHub answers with the same GitHub ID. When GitHub answers with another GitHub ID or not found, the refresh SHALL fetch the repository's metadata by GitHub ID first, as a metadata refresh does, and SHALL fetch the other data types under the name GitHub gives for that ID. Data that GitHub serves for another GitHub ID SHALL NOT be stored under the repository.

#### Scenario: Name taken before an issues refresh
- **WHEN** stored repository `org/tool` (GitHub ID 1) was renamed on GitHub to `org/tool-legacy`, a new repository `org/tool` (GitHub ID 2) was created and is not stored, and an issues-only refresh of GitHub ID 1 runs
- **THEN** the refresh fetches GitHub ID 1's metadata by ID, stores it as `org/tool-legacy`, and stores the issues of `org/tool-legacy`, never those of GitHub ID 2

#### Scenario: Same repository
- **WHEN** an issues-only refresh runs and GitHub answers the lookup of the stored name with the same GitHub ID
- **THEN** the refresh fetches and stores only the issues

#### Scenario: Deleted before a README refresh
- **WHEN** a README-only refresh runs, GitHub answers the stored name with not found, and answers the lookup by GitHub ID with not found
- **THEN** the repository is FAILED with error code `not_found` and ineligible with the reason `repository_unavailable`

### Requirement: Repository names compare case-insensitively
When storing a repository looks for a stored repository holding the same name (see "Analysis failures are recorded"), names SHALL be compared case-insensitively, as GitHub compares them. A holder whose stored name differs only in letter case SHALL give the name up as any other holder.

#### Scenario: Recreated with different case
- **WHEN** stored repository `Org/Tool` (GitHub ID 1) was deleted on GitHub, a new repository `org/tool` (GitHub ID 2) was created, and a search stores GitHub ID 2
- **THEN** GitHub ID 1 gives up its name, is ineligible as `name_released`, and its refresh is queued as for any released name

#### Scenario: Same repository with a case change
- **WHEN** a stored repository `org/Tool` is stored again under `org/tool` with the same GitHub ID
- **THEN** no name is released and the repository is stored as `org/tool`

### Requirement: Broker refusal while queuing a released name
When the refresh of a repository that released its name cannot be sent because the broker refuses the task, the change that released the name SHALL still succeed with everything it stored. The repository whose task was refused SHALL NOT count as queued, so the periodic background task can queue it, and every other repository of that change SHALL still have its refresh sent.

#### Scenario: Broker down after a search
- **WHEN** a discovery search stores `org/tool` (GitHub ID 3) while pooled repositories `Org/Tool` (GitHub ID 1) and `ORG/TOOL` (GitHub ID 2) hold that name, and the broker refuses the first of their two refresh tasks
- **THEN** the search's results stay stored and its step does not fail, the second task is sent, and the first repository is not stamped as queued
