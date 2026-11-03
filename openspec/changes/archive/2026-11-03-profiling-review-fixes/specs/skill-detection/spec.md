## MODIFIED Requirements

### Requirement: README skill evidence
The system SHALL extract skill evidence from the stored profile README by matching catalog aliases in skill- or technology-related sections (headings such as "Skills", "Tech Stack", "Tools", "Languages"), in badge images (for example shields.io `logo=` parameters and alt text) and in skill-icon image URLs. Aliases that are common English words or ambiguous (for example "Go", "Rust", "Spring", "Express") SHALL be matched only inside those sections, badges or icons, never in free text. A skill SHALL get at most one README evidence record however often it is mentioned. Content inside HTML comments SHALL provide no evidence, and a line inside a fenced code block SHALL never be read as a heading. A heading's title SHALL keep a trailing `#` that is part of a word (as in "C#"). A missing README SHALL produce no README evidence and SHALL NOT fail analysis.

#### Scenario: Skills section
- **WHEN** the README contains "## Tech Stack" followed by "Python, Django, React, Docker"
- **THEN** Python, Django, React and Docker each have one README evidence record

#### Scenario: Badge
- **WHEN** the README contains a shields.io badge with `logo=postgresql`
- **THEN** PostgreSQL has README evidence

#### Scenario: Ambiguous word in free text
- **WHEN** the README's introduction says "I like to go hiking" and no section, badge or icon mentions Go
- **THEN** the Go skill gets no README evidence

#### Scenario: Commented-out section
- **WHEN** the README contains a "## Tech stack" section listing Go and Rust inside `<!-- … -->`
- **THEN** neither Go nor Rust gets README evidence

#### Scenario: Comment in a code block
- **WHEN** a "## Skills" section lists Python, then a fenced shell block containing `# setup`, then Go
- **THEN** the section is not split at `# setup`, and Python and Go both have README evidence from the "Skills" section

#### Scenario: Unusual letter case
- **WHEN** the README contains a word with a Unicode case variant such as "Kotlın" (dotless ı)
- **THEN** analysis completes; the text either matches its catalog phrase or matches nothing

#### Scenario: No README
- **WHEN** the user has no profile README
- **THEN** analysis completes and no skill has README evidence

### Requirement: Dependency evidence
The system SHALL record dependency evidence for each catalog skill that a dependency of an owned non-fork repository maps to, naming the repository, the manifest and the dependency. The supported manifests are requirements.txt, pyproject.toml, package.json, go.mod, Cargo.toml, pom.xml, build.gradle and build.gradle.kts, read from the repository root. Dependencies that are commented out SHALL provide no evidence. A requirements.txt line naming a package by direct reference (`name @ URL`) SHALL count as that package. A manifest value of an unexpected type (for example a string where a list of dependencies is expected) SHALL provide no dependencies rather than being misread. A manifest that cannot be parsed SHALL be skipped without failing analysis.

#### Scenario: Python dependency
- **WHEN** an owned repository's pyproject.toml depends on `djangorestframework` and `celery`
- **THEN** Django REST Framework and Celery each have dependency evidence naming that repository and pyproject.toml

#### Scenario: Unparseable manifest
- **WHEN** a repository's package.json is not valid JSON
- **THEN** that manifest provides no evidence and analysis completes

#### Scenario: Commented-out dependency
- **WHEN** a pom.xml has a Spring Boot dependency only inside `<!-- … -->`, or a build.gradle has it only on a `//` line
- **THEN** Spring Boot gets no dependency evidence from that manifest

#### Scenario: Direct reference
- **WHEN** a requirements.txt contains `django @ https://example.com/django.whl`
- **THEN** Django has dependency evidence from that line

#### Scenario: Wrong value type
- **WHEN** a pyproject.toml declares `optional-dependencies = { dev = "pytest" }`
- **THEN** that group provides no dependencies (no single-letter names are stored)

### Requirement: Contribution evidence
The system SHALL record contribution evidence from repositories the user does not own:
- a merged pull request is `pull_request` evidence;
- a public push in the recent public activity GitHub provides is `commit` evidence;
- merged pull requests to the same repository reaching a configured count (default 3) are one `repeated_contribution` evidence record.

Each record SHALL be attributed to the skills of the contributed repository: its catalog languages (under the same share rule as owned repositories) and topics. Evidence SHALL name the contributed repository. Contributions to a forked repository SHALL provide no evidence. When contribution data is unavailable, analysis SHALL continue without it.

#### Scenario: Merged pull request
- **WHEN** the user has one merged pull request to `pallets/flask`, a Python repository
- **THEN** the Python skill has pull request evidence naming `pallets/flask`

#### Scenario: Repeated contribution
- **WHEN** the user has 4 merged pull requests to the same Go repository and the threshold is 3
- **THEN** the Go skill has one repeated contribution evidence record for that repository, in addition to its pull request evidence

#### Scenario: Contribution to a fork
- **WHEN** the user's only contributions are pushes to a forked Rust repository they do not own
- **THEN** no skill or interest gets evidence from that repository

#### Scenario: Contribution data unavailable
- **WHEN** GitHub search returned no usable contribution data for the user
- **THEN** skills are detected from the other sources and analysis completes
