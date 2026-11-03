# skill-detection Specification

## Purpose

Detects a developer's technical skills from their stored GitHub data. It records the evidence behind each skill and turns that evidence into a configurable confidence value, so the profile explains itself and a lone README mention never counts as much as sustained use.
## Requirements
### Requirement: Canonical skill catalog
The system SHALL detect skills only against a canonical skill catalog. Each skill has a stable identifier, a display name, one category (language, framework, library, database, cloud, devops or tool) and a set of aliases. Aliases, GitHub language names, repository topics and dependency names that refer to the same technology SHALL resolve to one skill. Terms that match no catalog entry SHALL NOT create skills.

#### Scenario: Aliases resolve to one skill
- **WHEN** a README mentions "Postgres", a repository has the topic `postgresql` and a manifest depends on `psycopg`
- **THEN** the developer has one PostgreSQL skill (category database) with three pieces of evidence

#### Scenario: Unknown term ignored
- **WHEN** a README skills section lists "FooBarFramework", which is not in the catalog
- **THEN** no skill is created for it

### Requirement: README skill evidence
The system SHALL extract skill evidence from the stored profile README by matching catalog aliases in skill- or technology-related sections (headings such as "Skills", "Tech Stack", "Tools", "Languages"), in badge images (for example shields.io `logo=` parameters and alt text) and in skill-icon image URLs. Aliases that are common English words or ambiguous (for example "Go", "Rust", "Spring", "Express") SHALL be matched only inside those sections, badges or icons, never in free text. A skill SHALL get at most one README evidence record however often it is mentioned. Content inside HTML comments SHALL provide no evidence (an unterminated comment hides the rest of the README, as GitHub renders it), and a line inside a fenced code block SHALL never be read as a heading (a fence closes only on a run of the same character, at least as long, with nothing after it). A heading's title SHALL keep a trailing `#` that is part of a word (as in "C#"). A missing README SHALL produce no README evidence and SHALL NOT fail analysis.

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

### Requirement: Repository language evidence
For each non-fork repository the user owns, the system SHALL record language evidence for every catalog language that is the repository's primary language or makes up at least a configured share of its bytes (default 10%). Each such repository SHALL be one evidence record that names the repository. Forked repositories SHALL NOT provide evidence.

#### Scenario: Language across repositories
- **WHEN** Python is at least 10% of the bytes in 8 of the user's owned non-fork repositories
- **THEN** the Python skill has 8 language evidence records, each naming its repository

#### Scenario: Minor language ignored
- **WHEN** Shell is 2% of a repository's bytes and not its primary language
- **THEN** that repository provides no Shell evidence

#### Scenario: Fork ignored
- **WHEN** a forked repository is written entirely in Rust
- **THEN** it provides no Rust evidence

### Requirement: Repository topic evidence
The system SHALL record topic evidence for each catalog skill that a topic of an owned non-fork repository maps to, naming the repository and the topic.

#### Scenario: Topic maps to skill
- **WHEN** an owned repository has the topics `django` and `rest-api`
- **THEN** the Django skill has topic evidence naming that repository and the topic `django`

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

### Requirement: Evidence records per skill
Every detected skill SHALL have at least one evidence record. Each record SHALL state its source (readme, language, topic, dependency, commit, pull_request or repeated_contribution), the supporting repository when there is one, a short factual detail (such as the matched topic, dependency or byte share) and when it was observed. For each skill the system SHALL provide the number of evidence records per source, the number of distinct supporting repositories and the most recent observation date. Evidence text SHALL come only from the data it was computed from.

#### Scenario: Evidence summary
- **WHEN** Python has README evidence, 8 language evidence records and 2 dependency evidence records across 8 distinct repositories
- **THEN** the Python skill reports readme 1, language 8, dependency 2, 8 supporting repositories and the latest observation date among them

### Requirement: Configurable evidence weights
Each evidence source SHALL have a weight between 0 and 1, taken from configuration. The defaults are readme 0.20, topic 0.30, language 0.50, dependency 0.60, commit 0.80, pull_request 0.90 and repeated_contribution 1.00. The system SHALL refuse to start if a configured weight is missing or outside 0–1. Each analyzed profile SHALL record the weights it was computed with.

#### Scenario: Invalid weight
- **WHEN** the configured language weight is 1.5
- **THEN** the startup checks report an error and the application does not start

#### Scenario: Weights recorded
- **WHEN** a profile is analyzed with the default weights
- **THEN** the profile records those weights

### Requirement: Confidence with diminishing returns
Each skill SHALL have a confidence between 0 and 1 (exclusive of 1), computed only from its evidence and the configured weights:
- more evidence SHALL never lower confidence;
- repeated evidence from the same source SHALL add progressively less;
- a skill whose only evidence is one README mention SHALL have confidence equal to the README weight.

The same evidence and weights SHALL always give the same confidence.

#### Scenario: README only
- **WHEN** a skill's only evidence is one README mention and the README weight is 0.20
- **THEN** its confidence is 0.20

#### Scenario: Sustained use outranks a mention
- **WHEN** skill A has only README evidence and skill B has language evidence in 5 repositories and dependency evidence in 2
- **THEN** skill B's confidence is higher than skill A's

#### Scenario: Diminishing returns
- **WHEN** a skill gains a 10th language evidence record
- **THEN** its confidence increases by less than it did when it gained its 2nd

#### Scenario: Weight change applies on re-analysis
- **WHEN** the README weight is changed to 0.10 and the profile is re-analyzed
- **THEN** a README-only skill's confidence becomes 0.10

