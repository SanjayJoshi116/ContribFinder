## MODIFIED Requirements

### Requirement: Export a developer snapshot
A management command SHALL export one user's stored developer features and candidate pool (with eligible issues) into the dataset format, for a person to judge. It SHALL make no GitHub calls. The export SHALL contain no username, name, email, GitHub id, avatar or token; the developer identifier SHALL be given by the person exporting. By default it SHALL also leave out every candidate the user interacted with (a repository they contributed to or that entered the pool as previously interacted with), because the set of those repositories identifies the person; an explicit option SHALL include them for private use. Every candidate SHALL be left unjudged, and the export SHALL say that judgments must be added by hand. A user without an analyzed profile SHALL produce an error, not an empty export.

#### Scenario: Anonymized export
- **WHEN** a person exports a user's snapshot with identifier `dev-f`
- **THEN** the file holds that user's skills, interests, experience level and candidates under `dev-f`, no identifying field of the user, and no judgments

#### Scenario: Interacted repositories left out
- **WHEN** the user's pool holds a repository found through search and a repository they contributed to, and the snapshot is exported without the include option
- **THEN** the file holds the searched repository and not the contributed one, and the command reports how many candidates were left out

#### Scenario: Interacted repositories on request
- **WHEN** the same snapshot is exported with the include option
- **THEN** both repositories are in the file

#### Scenario: Not analyzed
- **WHEN** the user has no developer profile
- **THEN** the command exits with an error and writes no file
