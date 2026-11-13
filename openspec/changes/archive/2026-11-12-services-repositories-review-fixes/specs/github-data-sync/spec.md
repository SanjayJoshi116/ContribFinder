## ADDED Requirements

### Requirement: Stored GitHub text
Every text value the system receives from GitHub (raw file contents such as READMEs, and every string in a JSON response: names, descriptions, topics, labels, issue titles and bodies, profile fields) SHALL be storable before anything stores it: NUL characters SHALL be removed, and unpaired UTF-16 surrogates (for example from a `\ud800` escape in JSON) SHALL be replaced by U+FFFD. Every other character SHALL be kept unchanged. Text that needed this cleaning SHALL NOT fail the request, the sync, the discovery search or the repository analysis that received it.

#### Scenario: NUL in a README
- **WHEN** a candidate repository's README contains NUL characters
- **THEN** its analysis completes, and the stored README is the same text without the NUL characters

#### Scenario: Unpaired surrogate in an issue
- **WHEN** an issue's body in GitHub's JSON contains the escape `\ud800` followed by `abc`
- **THEN** the issue is stored with U+FFFD in place of the surrogate, and the analysis completes

#### Scenario: NUL in a search result
- **WHEN** a discovery search returns a repository whose description contains the escape `\u0000`
- **THEN** the search stores its results, and that description is stored without the NUL

#### Scenario: Ordinary text unchanged
- **WHEN** a README holds emoji, accented letters and characters outside the Basic Multilingual Plane
- **THEN** it is stored exactly as received

## MODIFIED Requirements

### Requirement: Profile README ingestion
A sync SHALL look for the profile README in the repository named after the user's username, owned by the user. If it exists, the system SHALL store its raw content, unchanged except for the cleaning of "Stored GitHub text", and separately from any derived data. A missing profile README SHALL be recorded as absent and SHALL NOT fail the sync. A profile README that GitHub refuses to return for reasons other than a rate limit (a 403 that is not a rate limit, 451, or another non-retryable client error) SHALL record the README step as skipped, SHALL keep the previously stored README and its presence flag, and SHALL NOT fail the sync.

#### Scenario: Profile README present
- **WHEN** the repository `octocat/octocat` has a README containing "## Skills\nPython"
- **THEN** the stored profile README content equals that text exactly and the profile is marked as having a README

#### Scenario: Profile README with a NUL
- **WHEN** the profile README contains "Python" followed by a NUL character and "Go"
- **THEN** the sync completes, and the stored profile README is "PythonGo"

#### Scenario: No profile README
- **WHEN** the user has no `{username}/{username}` repository, or it has no README
- **THEN** the profile is marked as having no README, the sync completes successfully, and the README step reports "not found" rather than an error

#### Scenario: Profile README blocked
- **WHEN** the README request for `octocat/octocat` is answered with 451, and a README was stored by an earlier sync
- **THEN** the README step reports "skipped", the earlier README and its presence flag are kept, and the sync completes
