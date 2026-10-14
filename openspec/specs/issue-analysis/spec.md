# issue-analysis Specification

## Purpose

Turns stored GitHub issues into structured, evidence-backed facts: normalized labels, contribution type, difficulty and mentioned technologies, using deterministic rules only.

## Requirements

### Requirement: Label normalization
The system SHALL map each issue's raw labels to canonical label categories: `good_first_issue`, `help_wanted`, `documentation`, `bug`, `enhancement`, `refactoring`, `testing`, `frontend`, `backend`, `performance`, `security`, `infrastructure`, `design`. Matching SHALL be case-insensitive, SHALL treat spaces, hyphens and underscores alike, SHALL ignore a leading scope prefix such as `type:`, `kind/` or `area/`, and SHALL use a maintained alias list (for example `docs` → `documentation`, `good-first-issue` and `beginner friendly` → `good_first_issue`, `feature` → `enhancement`, `ci` → `infrastructure`). Labels that match no category SHALL be kept as raw labels only. Raw labels SHALL always be kept as GitHub sent them.

#### Scenario: Prefixed and aliased labels
- **WHEN** an issue has the labels `Type: Bug`, `docs` and `good-first-issue`
- **THEN** its canonical labels are `bug`, `documentation` and `good_first_issue`, and its raw labels are unchanged

#### Scenario: Unknown label
- **WHEN** an issue has the label `needs-triage`
- **THEN** it has no canonical label for it and the raw label is kept

### Requirement: Contribution type
The system SHALL classify each issue as one of `code`, `documentation`, `testing`, `bug_fix`, `feature`, `devops`, `design` or `unknown`. Canonical labels SHALL decide first, in a fixed priority order; title keywords SHALL decide only when no label applies; when neither applies the type SHALL be `unknown`. The classification SHALL record which label or keyword decided it.

#### Scenario: Label decides
- **WHEN** an issue has the canonical label `documentation`
- **THEN** its contribution type is `documentation` and the evidence names that label

#### Scenario: Keyword decides
- **WHEN** an issue has no categorized label and the title "Fix typo in README"
- **THEN** its contribution type is `documentation` and the evidence names the keyword

#### Scenario: No evidence
- **WHEN** an issue has no categorized label and no recognized keyword
- **THEN** its contribution type is `unknown`

### Requirement: Difficulty estimate
The system SHALL estimate each issue's difficulty as `beginner`, `intermediate`, `advanced` or `unknown` from several signals: difficulty-indicating labels (for example `good_first_issue`, `easy`, `medium`, `hard`), description length, the number of technologies the issue mentions, its contribution type, and its comment count, with thresholds from configuration. A level SHALL be assigned only when at least two signals point to it and no signal points to a different level; a label alone SHALL NOT decide difficulty. Otherwise the difficulty SHALL be `unknown`. The estimate SHALL store every signal it considered and which way each pointed.

#### Scenario: Beginner with support
- **WHEN** an issue is labeled `good first issue`, has a short description and mentions one technology
- **THEN** its difficulty is `beginner` and its evidence lists the label, the short description and the technology count

#### Scenario: Label alone
- **WHEN** an issue is labeled `good first issue` and no other signal points to any level
- **THEN** its difficulty is `unknown`

#### Scenario: Contradicting signals
- **WHEN** an issue is labeled `good first issue` but has a very long description and mentions four technologies
- **THEN** its difficulty is `unknown`

### Requirement: Issue technologies
The system SHALL detect the technologies an issue mentions in its title, labels and body using the same skill catalog and alias rules as for developers and repositories, recording where each was found. Ambiguous words SHALL follow the catalog's existing context rules.

#### Scenario: Technology in the title
- **WHEN** an issue's title is "Support async views in Django 5"
- **THEN** Django is among its technologies, with the title as the source

### Requirement: Analysis is deterministic and local
Issue analysis SHALL run from stored issue data only, SHALL NOT call GitHub, an LLM or an embedding service, and SHALL produce identical results for identical input and configuration. It SHALL run whenever a repository's issues are stored or refreshed.

#### Scenario: Re-run
- **WHEN** an unchanged issue is analyzed twice
- **THEN** its canonical labels, contribution type, difficulty, technologies and evidence are identical
