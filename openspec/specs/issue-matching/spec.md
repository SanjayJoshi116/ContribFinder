# issue-matching Specification

## Purpose

Points each developer at concrete issues in their recommended repositories that fit their demonstrated technologies and experience, explains why, and shows each issue with GitHub data kept apart from ContribFinder's analysis.

## Requirements

### Requirement: Eligible issues
An issue SHALL be eligible for matching only when it is open, not locked, has no assignee, and was updated on GitHub within a configured age (default 365 days). Ineligible issues SHALL NOT be recommended.

#### Scenario: Assigned issue
- **WHEN** an issue that otherwise matches the developer has an assignee
- **THEN** it is not recommended

### Requirement: Issue relevance
For each recommendation, the system SHALL score the repository's eligible issues for the developer from 0.0 to 1.0 using: technology match (the issue's technologies the developer has demonstrated, weighted by confidence), difficulty fit (the issue's difficulty against the developer's internal experience level, from a configured table, with `unknown` difficulty given a configured neutral value), and approachability (`good_first_issue` and `help_wanted` labels). The weights and table SHALL belong to the active scoring configuration. An issue SHALL be relevant only when its score reaches the configured minimum and it has a technology match or an approachability label. The system SHALL keep the best relevant issues per recommendation, up to a configured number (default 5), ranked by score, then most recently updated. Scoring SHALL use stored data only and SHALL be deterministic.

#### Scenario: Matching issue kept
- **WHEN** a recommended Django repository has an eligible beginner issue mentioning Django and the developer has Django skills
- **THEN** the issue is among the recommendation's relevant issues

#### Scenario: Unrelated issue
- **WHEN** an eligible issue mentions none of the developer's technologies and has no approachability label
- **THEN** it is not a relevant issue

#### Scenario: Cap
- **WHEN** a recommendation has 12 relevant issues and the cap is 5
- **THEN** only the 5 best are kept

### Requirement: Issue reasons
Every relevant issue SHALL have reasons generated only from the signals that scored it: the matched technologies, the difficulty and how it fits, and the approachability labels. A signal with value 0 SHALL produce no reason. Reason texts SHALL use words, never percentages, and SHALL describe difficulty as an estimate.

#### Scenario: Reasons
- **WHEN** an issue matched Django, is estimated beginner for a beginner developer, and is labeled `good first issue`
- **THEN** its reasons name Django, the estimated beginner difficulty, and the `good first issue` label

### Requirement: Relevant issues follow their recommendation
Relevant issues SHALL be regenerated with their recommendation and SHALL NOT outlive it. A dismissed recommendation's issues SHALL disappear with it.

#### Scenario: Issue closed between generations
- **WHEN** a relevant issue is closed and the repository's issues are refreshed before the next generation
- **THEN** the next generation no longer lists it

### Requirement: Issue detail endpoint
The system SHALL provide `GET /api/v1/issues/{id}` for an issue that is a relevant issue of one of the requesting user's current recommendations, and SHALL return 404 otherwise. The response SHALL separate GitHub data (repository full name, number, title, body as plain text, raw labels, state, comment count, creation and update times, URL) from ContribFinder analysis (canonical labels, contribution type and its evidence, estimated difficulty and its evidence, technologies with the developer's matched ones marked, reasons, and the recommendation it belongs to). It SHALL NOT contain a numeric score. It SHALL return 401 when signed out.

#### Scenario: Own issue
- **WHEN** a user requests a relevant issue of one of their recommendations
- **THEN** the response contains the GitHub data and the analysis as separate sections, without a score

#### Scenario: Not relevant to the user
- **WHEN** a user requests an issue that is not a relevant issue of any of their recommendations
- **THEN** the response is 404

### Requirement: Issue detail page
Selecting a relevant issue SHALL open an issue detail page showing the title, repository, labels, description, contribution type, estimated difficulty, match reasons and a link that opens the issue on GitHub. Content from GitHub SHALL be visually distinguishable from ContribFinder's analysis. The description SHALL be rendered as plain text, never as HTML. An `unknown` difficulty or contribution type SHALL be shown as "Not enough evidence", not as an error. An issue URL whose id is not a positive integer SHALL say that the link does not point to an issue and offer the way back to the dashboard, without requesting anything.

#### Scenario: Issue page
- **WHEN** the user opens a relevant issue
- **THEN** the page shows its GitHub data and ContribFinder analysis in separate sections, and a GitHub link

#### Scenario: Unknown difficulty
- **WHEN** the issue's difficulty is `unknown`
- **THEN** the page shows "Not enough evidence" for difficulty

#### Scenario: Invalid id
- **WHEN** the user opens `/app/issues/x`
- **THEN** the page says the link does not point to an issue, links back to the dashboard, and never shows "Loading…" indefinitely
