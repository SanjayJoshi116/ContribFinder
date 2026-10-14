## MODIFIED Requirements

### Requirement: Feedback events
The system SHALL record a feedback event for a user's recommendation interactions: `viewed`, `saved`, `unsaved`, `dismissed`, `undismissed`, `opened_repository` and `opened_issue`. Each event SHALL store the user, the repository, the recommendation it came from (when it still exists), the action, the time, and a snapshot of the recommendation's match label, rank and scoring configuration version at that moment. An `opened_issue` event SHALL also store the issue (while it still exists) and a snapshot of its number. Events SHALL remain intact when the recommendation is regenerated or removed, or when the issue is closed or removed. `POST /api/v1/recommendations/{id}/feedback` SHALL accept `viewed`, `opened_repository` and `opened_issue` for the requesting user's own recommendations; `opened_issue` SHALL require the id of one of that recommendation's relevant issues and SHALL be rejected with a 400 error otherwise. Saved, dismissed and their reversals SHALL be recorded by the save and dismiss actions themselves. A `viewed` event for the same user and recommendation within the configured window (default 30 minutes) SHALL NOT create a second event. Feedback SHALL NOT change scores or ranking.

#### Scenario: View recorded once
- **WHEN** a user opens the same recommendation's detail page twice within 30 minutes
- **THEN** one `viewed` event exists, with the match label, rank and config version the recommendation had

#### Scenario: Opened on GitHub
- **WHEN** a user follows a recommendation's GitHub link
- **THEN** an `opened_repository` event is recorded

#### Scenario: Issue opened on GitHub
- **WHEN** a user follows the GitHub link of one of a recommendation's relevant issues
- **THEN** an `opened_issue` event is recorded with that issue and its number

#### Scenario: Issue not part of the recommendation
- **WHEN** a user posts `opened_issue` with an issue id that is not a relevant issue of that recommendation
- **THEN** the response is 400 and no event is stored

#### Scenario: Feedback outlives the recommendation
- **WHEN** a recommendation that has feedback events drops out of a later regeneration
- **THEN** its feedback events still exist, with their repository and snapshot

#### Scenario: Someone else's recommendation
- **WHEN** user A posts feedback for a recommendation id that belongs to user B
- **THEN** the response is 404 and no event is stored

#### Scenario: No ranking effect
- **WHEN** a user has viewed a recommendation many times
- **THEN** its score and rank in the next generation are the same as without the views
