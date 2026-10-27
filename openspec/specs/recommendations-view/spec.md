# recommendations-view Specification

## Purpose

Lets a signed-in developer browse, filter and inspect their repository recommendations, each presented with why it matches and the observable facts behind it, from stored data only.

## Requirements

### Requirement: Recommendation list endpoint
The system SHALL provide `GET /api/v1/recommendations`: a paginated list of the requesting user's recommendations in rank order. Each item SHALL contain its id; the repository's full name, owner, name, description, URL, primary language, stars, topics and license; the match label; the repository's technologies, with the ones the developer has demonstrated marked as matched; the reasons (type, text, detail); the activity label; the repository size class; the contribution openness facts; the number of relevant issues; and the generation time. Items SHALL NOT contain the numeric score or rank. The endpoint SHALL be served from stored data only, with a query count that does not grow with the page size, and SHALL return 401 when signed out.

#### Scenario: Ranked list
- **WHEN** the user has 25 recommendations and requests the first page
- **THEN** they are returned best first, each with its match label, reasons and relevant issue count, and without a score

#### Scenario: Another user's recommendations
- **WHEN** user A requests the list
- **THEN** no recommendation of user B is returned

### Requirement: Recommendation filters
The list SHALL be filterable by:
- **language**: repositories with code in that language (case-insensitive);
- **framework**: repositories whose technologies include that framework or skill (catalog slug);
- **activity**: `recently_active`, `moderately_active`, `low_activity`;
- **size**: `small`, `medium`, `large`, `unknown`, from the repository's contributor count with configured thresholds (default: small under 10 contributors, medium under 100, large otherwise; unknown when the count is unknown);
- **match**: `strong`, `good`, `partial`;
- **difficulty**: `beginner`, `intermediate`, `advanced`, `unknown`: recommendations with at least one relevant issue of that estimated difficulty;
- **contribution_type**: `code`, `documentation`, `testing`, `bug_fix`, `feature`, `devops`, `design`: recommendations with at least one relevant issue of that contribution type.

Filters SHALL combine with AND. An unknown filter value SHALL be rejected with a 400 error.

#### Scenario: Language and activity
- **WHEN** the user requests `?language=python&activity=recently_active`
- **THEN** only recently active repositories with Python code are returned, still in rank order

#### Scenario: Difficulty
- **WHEN** the user requests `?difficulty=beginner`
- **THEN** only recommendations with at least one relevant issue estimated beginner are returned, still in rank order

#### Scenario: Contribution type
- **WHEN** the user requests `?contribution_type=documentation`
- **THEN** only recommendations with at least one relevant documentation issue are returned

#### Scenario: Invalid value
- **WHEN** the user requests `?activity=healthy`
- **THEN** the response is 400 with the standard error envelope

### Requirement: Recommendation detail endpoint
The system SHALL provide `GET /api/v1/recommendations/{id}` returning everything in a list item plus: the repository's language breakdown, a README excerpt (plain text, capped length, empty when there is no README), the contribution guideline facts (contribution guide, code of conduct, issue and pull request templates, `good first issue` and `help wanted` labels), the activity signals (days since last push, commits and merged pull requests in 90 days, contributor count, latest release date, open issues), and its relevant issues in order, each with its id, number, title, URL, canonical labels, contribution type, estimated difficulty and reasons, without a score. List items and the detail SHALL include the repository's setup facts (CI, tests, dev environment, Docker Compose), each found, not found or unknown (null). It SHALL return 404 for a recommendation that does not exist or belongs to another user.

#### Scenario: Detail
- **WHEN** the user opens one of their recommendations
- **THEN** the response includes the README excerpt, the language breakdown, the contribution guideline facts, the setup facts, the activity signals and the relevant issues

#### Scenario: Someone else's recommendation
- **WHEN** user A requests a recommendation id that belongs to user B
- **THEN** the response is 404

#### Scenario: Setup facts unknown
- **WHEN** a recommended repository has not been analyzed for setup facts yet
- **THEN** each of its setup facts is null in the list item and the detail

### Requirement: Recommendation status endpoint
The system SHALL provide `GET /api/v1/recommendations/status` with the user's latest recommendation generation job (or null), the time recommendations were last generated, the number of recommendations, and the version of the configuration that produced them.

#### Scenario: Never generated
- **WHEN** a user has never had recommendations generated
- **THEN** the status has no job, no generation time and a count of 0

### Requirement: Recommendations on the dashboard
The signed-in dashboard SHALL show the user's recommendations as cards. Each card SHALL show the repository name and owner, description, technologies (matched ones highlighted), the match label as text (Strong match, Good match, Partial match), the top reasons, the activity indicator as an observable signal (for example "Recently active", never "healthy"), the setup facts found as one short line (for example "CI · tests · dev container"; nothing when none was found or they are unknown), the number of relevant issues when there are any, and a link that opens the repository on GitHub. The dashboard SHALL offer the language, framework, activity, size, match, difficulty and contribution type filters when the user has more recommendations than fit on one page (20), or when a filter is already active; it SHALL keep them in the URL and update the list without a page reload. With one page or fewer and no active filter, the filters SHALL be hidden. While recommendations are being generated it SHALL say so; with none it SHALL explain why (for example discovery still running or no eligible projects). It SHALL NOT show percentages or numeric scores. A page number in the URL past the last page SHALL move to the first page instead of showing an error, and a page left empty by dismissals while earlier pages exist SHALL move to the previous page instead of saying there are no recommendations; both SHALL replace the URL, not add a history entry.

#### Scenario: Cards with reasons
- **WHEN** the user has recommendations
- **THEN** each card shows its match label, top reasons, technologies, activity indicator and a GitHub link, and no percentage

#### Scenario: Relevant issue count
- **WHEN** a recommendation has 3 relevant issues
- **THEN** its card says 3 relevant issues

#### Scenario: Few recommendations
- **WHEN** the user has 10 recommendations and no filter in the URL
- **THEN** all 10 are listed and no filter controls are shown

#### Scenario: Filter in the URL
- **WHEN** the user has more than 20 recommendations and selects the Python language filter
- **THEN** the list shows only matching recommendations and the URL contains the filter, so a reload keeps it

#### Scenario: Generating
- **WHEN** the user's recommendation generation job is active
- **THEN** the dashboard says recommendations are being prepared and updates when the job completes, without a reload

#### Scenario: Page past the end
- **WHEN** the user opens `/app?page=5` and there are 2 pages of recommendations
- **THEN** the first page is shown, the URL has no page number, and no error is shown

#### Scenario: Last card on a page dismissed
- **WHEN** the user is on page 2, which holds one recommendation, and dismisses it
- **THEN** page 1 is shown, with the Undo notice still visible

#### Scenario: Setup line on a card
- **WHEN** a recommended repository has CI and tests found, no dev environment and no Docker Compose found
- **THEN** its card shows "CI · tests" and does not mention the facts not found

#### Scenario: No setup line
- **WHEN** a recommended repository's setup facts are all not found, or all unknown
- **THEN** its card shows no setup line

### Requirement: Repository detail page
Selecting a recommendation SHALL open a repository detail page with: an overview (name, owner, description, stars, license, GitHub link), why it matches (all reasons), technologies, topics, activity signals, contribution guidelines, setup facts, the README excerpt, and its relevant issues, each showing title, contribution type, estimated difficulty and its top reason and linking to the issue detail page. Each setup fact SHALL read "Found", "Not found" or "Not available" (unknown), never "No", because detection only looks at the repository root. Content that comes directly from GitHub SHALL be visually distinguishable from ContribFinder's analysis. A missing README, unknown signal or absence of relevant issues SHALL be shown as unavailable, not as an error. Following a card's relevant-issue count SHALL open the page scrolled to its relevant issues, with keyboard focus on that section once it has loaded; the scroll SHALL NOT animate when the user prefers reduced motion. A detail URL whose id is not a positive integer SHALL say that the link does not point to a recommendation and offer the way back to the dashboard, without requesting anything.

#### Scenario: Detail page
- **WHEN** the user opens a recommendation
- **THEN** the page shows why it matches, its technologies, topics, activity signals, contribution guidelines, setup facts, README excerpt and relevant issues, with a link to GitHub

#### Scenario: No README
- **WHEN** the repository has no README
- **THEN** the README section says none is available and the rest of the page renders

#### Scenario: No relevant issues
- **WHEN** the recommendation has no relevant issues
- **THEN** the relevant issues section says none were found for the developer and the rest of the page renders

#### Scenario: Relevant issues link
- **WHEN** the user follows "3 relevant issues" on a card
- **THEN** after the page loads, the relevant issues section is in view and has keyboard focus

#### Scenario: Invalid id
- **WHEN** the user opens `/app/recommendations/abc` or `/app/recommendations/0`
- **THEN** the page says the link does not point to a recommendation, links back to the dashboard, and never shows "Loading…" indefinitely

#### Scenario: Setup facts on the detail page
- **WHEN** the repository has tests found, CI not found and its dev environment and Docker Compose facts unknown
- **THEN** the Setup group reads tests "Found", CI "Not found", dev environment "Not available" and Docker Compose "Not available"
