## MODIFIED Requirements

### Requirement: Issue detail page
Selecting a relevant issue SHALL open an issue detail page showing the title, repository, labels, description, contribution type, estimated difficulty, match reasons and a link that opens the issue on GitHub. Content from GitHub SHALL be visually distinguishable from ContribFinder's analysis. The description SHALL be rendered as plain text, never as HTML. An `unknown` difficulty or contribution type SHALL be shown as "Not enough evidence", not as an error. When a label decided the contribution type, the page SHALL name the label's category (for example "From a documentation label"), never present the category as a label name the issue may not carry. The difficulty basis SHALL list only signals the page knows how to describe. An issue that mentions no technology SHALL say so ("No technologies mentioned"), not that evidence is missing. An issue URL whose id is not a positive integer SHALL say that the link does not point to an issue and offer the way back to the dashboard, without requesting anything.

#### Scenario: Issue page
- **WHEN** the user opens a relevant issue
- **THEN** the page shows its GitHub data and ContribFinder analysis in separate sections, and a GitHub link

#### Scenario: Unknown difficulty
- **WHEN** the issue's difficulty is `unknown`
- **THEN** the page shows "Not enough evidence" for difficulty

#### Scenario: Invalid id
- **WHEN** the user opens `/app/issues/x`
- **THEN** the page says the link does not point to an issue, links back to the dashboard, and never shows "Loading…" indefinitely

#### Scenario: Type decided by a scoped label
- **WHEN** an issue labeled `kind/docs` is classified as documentation by its label
- **THEN** the page says the type comes from a documentation label, and does not quote "documentation" as a label

#### Scenario: Unknown difficulty signal
- **WHEN** the stored difficulty evidence holds a signal the page does not know
- **THEN** that signal is left out of the difficulty basis

#### Scenario: No technologies
- **WHEN** a relevant issue mentions no technology
- **THEN** the page says "No technologies mentioned"
