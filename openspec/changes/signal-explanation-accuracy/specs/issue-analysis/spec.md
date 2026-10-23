## MODIFIED Requirements

### Requirement: Label normalization
The system SHALL map each issue's raw labels to canonical label categories: `good_first_issue`, `help_wanted`, `documentation`, `bug`, `enhancement`, `refactoring`, `testing`, `frontend`, `backend`, `performance`, `security`, `infrastructure`, `design`. Matching SHALL be case-insensitive, SHALL treat spaces, hyphens and underscores alike, SHALL ignore a leading scope prefix such as `type:`, `kind/`, `area/` or a bracketed one such as `[Type]`, and SHALL use a maintained alias list (for example `docs` → `documentation`, `good-first-issue` and `beginner friendly` → `good_first_issue`, `feature` → `enhancement`, `ci` → `infrastructure`). Labels that match no category SHALL be kept as raw labels only. Raw labels SHALL always be kept as GitHub sent them.

#### Scenario: Prefixed and aliased labels
- **WHEN** an issue has the labels `Type: Bug`, `docs` and `good-first-issue`
- **THEN** its canonical labels are `bug`, `documentation` and `good_first_issue`, and its raw labels are unchanged

#### Scenario: Unknown label
- **WHEN** an issue has the label `needs-triage`
- **THEN** it has no canonical label for it and the raw label is kept

#### Scenario: Bracketed scope
- **WHEN** an issue has the labels `[Type] Bug` and `[Area] Docs`
- **THEN** its canonical labels are `bug` and `documentation`

### Requirement: Difficulty estimate
The system SHALL estimate each issue's difficulty as `beginner`, `intermediate`, `advanced` or `unknown` from several signals: difficulty-indicating labels (for example `good_first_issue`, `easy`, `medium`, `hard`), description length (ignoring HTML comments, such as the hints an issue template leaves in the description), the number of technologies the issue mentions, its contribution type, and its comment count, with every threshold from configuration, including the number of technologies that votes intermediate and the number of agreeing signals a level needs (default two). A level SHALL be assigned only when at least that many signals, and never fewer than two, point to it and no signal points to a different level; a label alone SHALL NOT decide difficulty. Otherwise the difficulty SHALL be `unknown`. The estimate SHALL store every signal it considered and which way each pointed.

#### Scenario: Beginner with support
- **WHEN** an issue is labeled `good first issue`, has a short description and mentions one technology
- **THEN** its difficulty is `beginner` and its evidence lists the label, the short description and the technology count

#### Scenario: Label alone
- **WHEN** an issue is labeled `good first issue` and no other signal points to any level
- **THEN** its difficulty is `unknown`

#### Scenario: Contradicting signals
- **WHEN** an issue is labeled `good first issue` but has a very long description and mentions four technologies
- **THEN** its difficulty is `unknown`

#### Scenario: Template hints not counted
- **WHEN** an issue's description is a two-line report inside an issue template whose HTML comments make it longer than the long-description threshold
- **THEN** the description-length signal measures the report without the comments and votes as a short description
