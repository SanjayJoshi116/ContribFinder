## MODIFIED Requirements

### Requirement: Repository data collection
For each candidate repository the system SHALL collect and store:
- metadata: owner, name, description, URL, default branch, stars, forks, open issues, primary language, license, creation, update and push dates, archived and fork flags;
- languages (bytes) and topics;
- the README;
- whether it has CONTRIBUTING documentation, a code of conduct, issue templates and a pull request template;
- whether it has a `good first issue` and a `help wanted` label;
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
