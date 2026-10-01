# recommendations-view Specification

## Purpose

Lets a signed-in developer browse, filter and inspect their repository recommendations, each presented with why it matches and the observable facts behind it, from stored data only.

## Requirements

### Requirement: Recommendation list endpoint
The system SHALL provide `GET /api/v1/recommendations`: a paginated list of the requesting user's recommendations in rank order. Each item SHALL contain its id; the repository's full name, owner, name, description, URL, primary language, stars, topics and license; the match label; the repository's technologies, with the ones the developer has demonstrated marked as matched; the reasons (type, text, detail); the activity label; the repository size class; the contribution openness facts; and the generation time. Items SHALL NOT contain the numeric score or rank. The endpoint SHALL be served from stored data only, with a query count that does not grow with the page size, and SHALL return 401 when signed out.

#### Scenario: Ranked list
- **WHEN** the user has 25 recommendations and requests the first page
- **THEN** they are returned best first, each with its match label and reasons, and without a score

#### Scenario: Another user's recommendations
- **WHEN** user A requests the list
- **THEN** no recommendation of user B is returned

### Requirement: Recommendation filters
The list SHALL be filterable by:
- **language**: repositories with code in that language (case-insensitive);
- **framework**: repositories whose technologies include that framework or skill (catalog slug);
- **activity**: `recently_active`, `moderately_active`, `low_activity`;
- **size**: `small`, `medium`, `large`, `unknown`, from the repository's contributor count with configured thresholds (default: small under 10 contributors, medium under 100, large otherwise; unknown when the count is unknown);
- **match**: `strong`, `good`, `partial`.

Filters SHALL combine with AND. An unknown filter value SHALL be rejected with a 400 error. Difficulty and contribution-type filters are not part of this capability.

#### Scenario: Language and activity
- **WHEN** the user requests `?language=python&activity=recently_active`
- **THEN** only recently active repositories with Python code are returned, still in rank order

#### Scenario: Invalid value
- **WHEN** the user requests `?activity=healthy`
- **THEN** the response is 400 with the standard error envelope

### Requirement: Recommendation detail endpoint
The system SHALL provide `GET /api/v1/recommendations/{id}` returning everything in a list item plus: the repository's language breakdown, a README excerpt (plain text, capped length, empty when there is no README), the contribution guideline facts (contribution guide, code of conduct, issue and pull request templates, `good first issue` and `help wanted` labels), and the activity signals (days since last push, commits and merged pull requests in 90 days, contributor count, latest release date, open issues). It SHALL return 404 for a recommendation that does not exist or belongs to another user.

#### Scenario: Detail
- **WHEN** the user opens one of their recommendations
- **THEN** the response includes the README excerpt, the language breakdown, the contribution guideline facts and the activity signals

#### Scenario: Someone else's recommendation
- **WHEN** user A requests a recommendation id that belongs to user B
- **THEN** the response is 404

### Requirement: Recommendation status endpoint
The system SHALL provide `GET /api/v1/recommendations/status` with the user's latest recommendation generation job (or null), the time recommendations were last generated, the number of recommendations, and the version of the configuration that produced them.

#### Scenario: Never generated
- **WHEN** a user has never had recommendations generated
- **THEN** the status has no job, no generation time and a count of 0

### Requirement: Recommendations on the dashboard
The signed-in dashboard SHALL show the user's recommendations as cards. Each card SHALL show the repository name and owner, description, technologies (matched ones highlighted), the match label as text (Strong match, Good match, Partial match), the top reasons, the activity indicator as an observable signal (for example "Recently active", never "healthy"), and a link that opens the repository on GitHub. The dashboard SHALL offer the language, framework, activity, size and match filters when the user has more recommendations than fit on one page (20), or when a filter is already active; it SHALL keep them in the URL and update the list without a page reload. With one page or fewer and no active filter, the filters SHALL be hidden. While recommendations are being generated it SHALL say so; with none it SHALL explain why (for example discovery still running or no eligible projects). It SHALL NOT show percentages or numeric scores.

#### Scenario: Cards with reasons
- **WHEN** the user has recommendations
- **THEN** each card shows its match label, top reasons, technologies, activity indicator and a GitHub link, and no percentage

#### Scenario: Few recommendations
- **WHEN** the user has 10 recommendations and no filter in the URL
- **THEN** all 10 are listed and no filter controls are shown

#### Scenario: Filter in the URL
- **WHEN** the user has more than 20 recommendations and selects the Python language filter
- **THEN** the list shows only matching recommendations and the URL contains the filter, so a reload keeps it

#### Scenario: Generating
- **WHEN** the user's recommendation generation job is active
- **THEN** the dashboard says recommendations are being prepared and updates when the job completes, without a reload

### Requirement: Repository detail page
Selecting a recommendation SHALL open a repository detail page with: an overview (name, owner, description, stars, license, GitHub link), why it matches (all reasons), technologies, topics, activity signals, contribution guidelines, and the README excerpt. Content that comes directly from GitHub SHALL be visually distinguishable from ContribFinder's analysis. A missing README or unknown signal SHALL be shown as unavailable, not as an error.

#### Scenario: Detail page
- **WHEN** the user opens a recommendation
- **THEN** the page shows why it matches, its technologies, topics, activity signals, contribution guidelines and README excerpt, with a link to GitHub

#### Scenario: No README
- **WHEN** the repository has no README
- **THEN** the README section says none is available and the rest of the page renders
