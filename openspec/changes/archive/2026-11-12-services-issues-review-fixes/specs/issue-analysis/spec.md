## MODIFIED Requirements

### Requirement: Label normalization
The system SHALL map each issue's raw labels to canonical label categories: `good_first_issue`, `help_wanted`, `documentation`, `bug`, `enhancement`, `refactoring`, `testing`, `frontend`, `backend`, `performance`, `security`, `infrastructure`, `design`. Matching SHALL be case-insensitive, SHALL treat spaces, hyphens and underscores alike, SHALL ignore a leading scope prefix such as `type:`, `kind/`, `area/` or a bracketed one such as `[Type]`, and SHALL use a maintained alias list (for example `docs` → `documentation`, `good-first-issue` and `beginner friendly` → `good_first_issue`, `feature` → `enhancement`, `ci` → `infrastructure`). A label without such a punctuated scope whose first word is on a maintained list of scope words (for example `type`, `kind`, `area`, `category`, and the single letters `c`, `e` and `t` that some projects use) SHALL have that word as its scope, so `type-bug` reads as `bug` and `E-easy` as `easy`. Labels that match no category SHALL be kept as raw labels only. Raw labels SHALL always be kept as GitHub sent them.

#### Scenario: Prefixed and aliased labels
- **WHEN** an issue has the labels `Type: Bug`, `docs` and `good-first-issue`
- **THEN** its canonical labels are `bug`, `documentation` and `good_first_issue`, and its raw labels are unchanged

#### Scenario: Unknown label
- **WHEN** an issue has the label `needs-triage`
- **THEN** it has no canonical label for it and the raw label is kept

#### Scenario: Bracketed scope
- **WHEN** an issue has the labels `[Type] Bug` and `[Area] Docs`
- **THEN** its canonical labels are `bug` and `documentation`

#### Scenario: Hyphen scope
- **WHEN** an issue has the labels `type-bug`, `C-feature-request` and `kind-documentation`
- **THEN** its canonical labels are `bug`, `enhancement` and `documentation`

#### Scenario: Label that only looks scoped
- **WHEN** an issue has the labels `good first issue` and `help wanted`
- **THEN** its canonical labels are `good_first_issue` and `help_wanted`

### Requirement: Difficulty estimate
The system SHALL estimate each issue's difficulty as `beginner`, `intermediate`, `advanced` or `unknown` from several signals: difficulty-indicating labels (for example `good_first_issue`, `easy`, `medium`, `hard`), description length (ignoring HTML comments, such as the hints an issue template leaves in the description, and fenced code blocks, such as pasted logs and stack traces), the number of technologies the issue mentions, its contribution type, and its comment count, with every threshold from configuration, including the number of technologies that votes intermediate and the number of agreeing signals a level needs (default two). A scoped label SHALL indicate a difficulty only when its scope is a difficulty scope (for example `difficulty:`, `level/`, `complexity:`, `E-`); a label under another scope (for example `Priority: Medium`, `severity: trivial`) SHALL NOT vote. The number of technologies that votes intermediate SHALL be lower than the number that votes advanced, so both can vote. A level SHALL be assigned only when at least that many signals, and never fewer than two, point to it and no signal points to a different level; a label alone SHALL NOT decide difficulty. Otherwise the difficulty SHALL be `unknown`. The estimate SHALL store every signal it considered and which way each pointed.

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

#### Scenario: Priority label does not vote
- **WHEN** an issue is labeled `good first issue` and `Priority: Medium`, has a short description and mentions one technology
- **THEN** its difficulty is `beginner`, and the priority label casts no vote

#### Scenario: Difficulty scope votes
- **WHEN** an issue is labeled `E-easy`, has a short description and mentions one technology
- **THEN** its difficulty is `beginner`, with the label among the beginner votes

#### Scenario: Pasted traceback not counted
- **WHEN** an issue's description is one sentence followed by a fenced code block holding a 4,500-character stack trace, and the long-description threshold is 4,000
- **THEN** the description-length signal measures the sentence only and votes as a short description

#### Scenario: Equal technology thresholds refused
- **WHEN** the configuration sets the technology count that votes intermediate equal to the one that votes advanced
- **THEN** the startup checks report it as an error

### Requirement: Issue technologies
The system SHALL detect the technologies an issue mentions in its title, labels and body using the same skill catalog and alias rules as for developers and repositories, recording where each was found. Ambiguous words SHALL follow the catalog's existing context rules: never in the title or body, and in a label only in its value after the scope, never as the scope itself (so `C-bug` and `C-feature-request` do not mean C, while `C`, `lang: go` and `React Hooks` mean C, Go and React). Unambiguous catalog phrases SHALL count anywhere in a label. HTML comments in the body SHALL be ignored, also when they contain `>` or are never closed.

#### Scenario: Technology in the title
- **WHEN** an issue's title is "Support async views in Django 5"
- **THEN** Django is among its technologies, with the title as the source

#### Scenario: Scope word is not a technology
- **WHEN** an issue has the labels `C-bug` and `C-feature-request`
- **THEN** C is not among its technologies

#### Scenario: Ambiguous word as the whole label
- **WHEN** an issue has the labels `lang: go` and `React Hooks`
- **THEN** Go and React are among its technologies, with the labels as the source

#### Scenario: Technology inside a template comment
- **WHEN** an issue's body holds `<!-- e.g. Python >= 3.10, Node.js 20 -->` and then "The button does nothing"
- **THEN** neither Python nor Node.js is among its technologies
