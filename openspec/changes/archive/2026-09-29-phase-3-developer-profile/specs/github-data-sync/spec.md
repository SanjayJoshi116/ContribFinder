## ADDED Requirements

### Requirement: Dependency manifest ingestion
A sync SHALL read root-level dependency manifests for the user's most recently pushed owned non-fork repositories, up to a configured number of repositories (default 30). The supported manifests are requirements.txt, pyproject.toml, package.json, go.mod, Cargo.toml, pom.xml, build.gradle and build.gradle.kts. For each repository the system SHALL store the dependency names found per ecosystem and manifest, replacing the previous set on each sync. Raw manifest contents SHALL NOT be stored. Manifests larger than a configured size SHALL be skipped. An empty repository, a repository without supported manifests, or a manifest that cannot be fetched (not found or forbidden) SHALL be skipped without failing the sync. Rate limits and transient failures SHALL be handled as for other sync requests, and a retried sync SHALL NOT re-read repositories it already finished.

#### Scenario: Manifests stored
- **WHEN** an owned repository has package.json with dependencies `react` and `vite` at its root
- **THEN** the repository's stored dependencies are `react` and `vite` for the npm ecosystem from package.json

#### Scenario: Repository without manifests
- **WHEN** an owned repository has no supported manifest at its root
- **THEN** it has no stored dependencies and the sync completes

#### Scenario: Repository cap
- **WHEN** the user owns 50 non-fork repositories and the cap is 30
- **THEN** manifests are read only for the 30 most recently pushed, and the job metadata records that the cap was applied

#### Scenario: Forks skipped
- **WHEN** an owned repository is a fork
- **THEN** its manifests are not read

### Requirement: External contribution ingestion
A sync SHALL collect the user's public contributions to repositories they do not own:
- merged pull requests authored by the user, up to a configured number;
- public push activity in the recent public events GitHub provides.

For the contributed repositories with the most contributions, up to a configured number (default 20), the system SHALL store repository metadata, languages and topics as for owned repositories. It SHALL link them to the user as contributor with the number of merged pull requests and pushes observed, and the time of the latest one. Contributor links that are no longer observed SHALL be removed on the next successful sync. Private activity SHALL NOT be requested. If GitHub rejects the contribution search for the user as invalid, the step SHALL be recorded as skipped and the sync SHALL complete.

#### Scenario: Merged pull requests recorded
- **WHEN** the user has 3 merged pull requests to `pallets/flask` and 1 to `psf/requests`
- **THEN** both repositories are stored with languages and topics, and linked to the user as contributor with 3 and 1 merged pull requests

#### Scenario: Own repositories excluded
- **WHEN** the user has merged pull requests to a repository they own
- **THEN** that repository is not linked as a contributed repository

#### Scenario: Contribution search rejected
- **WHEN** GitHub answers the contribution search with 422
- **THEN** the contributions step is skipped and the sync completes

#### Scenario: Contribution repository cap
- **WHEN** the user contributed to 35 repositories and the cap is 20
- **THEN** only the 20 repositories with the most contributions are stored and linked, and the job metadata records that the cap was applied
