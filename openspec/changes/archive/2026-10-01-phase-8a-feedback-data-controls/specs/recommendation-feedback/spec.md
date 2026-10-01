## Purpose

Lets developers act on their recommendations (save the ones they want to keep, dismiss the ones they don't) and records their interactions as feedback that is stored independently of the recommendations, for later analytics and evaluation.

## ADDED Requirements

### Requirement: Feedback events
The system SHALL record a feedback event for a user's recommendation interactions: `viewed`, `saved`, `unsaved`, `dismissed`, `undismissed`, `opened_repository` and `opened_issue`. Each event SHALL store the user, the repository, the recommendation it came from (when it still exists), the action, the time, and a snapshot of the recommendation's match label, rank and scoring configuration version at that moment. Events SHALL remain intact when the recommendation is regenerated or removed. `POST /api/v1/recommendations/{id}/feedback` SHALL accept `viewed`, `opened_repository` and `opened_issue` for the requesting user's own recommendations; saved, dismissed and their reversals SHALL be recorded by the save and dismiss actions themselves. A `viewed` event for the same user and recommendation within the configured window (default 30 minutes) SHALL NOT create a second event. Feedback SHALL NOT change scores or ranking.

#### Scenario: View recorded once
- **WHEN** a user opens the same recommendation's detail page twice within 30 minutes
- **THEN** one `viewed` event exists, with the match label, rank and config version the recommendation had

#### Scenario: Opened on GitHub
- **WHEN** a user follows a recommendation's GitHub link
- **THEN** an `opened_repository` event is recorded

#### Scenario: Feedback outlives the recommendation
- **WHEN** a recommendation that has feedback events drops out of a later regeneration
- **THEN** its feedback events still exist, with their repository and snapshot

#### Scenario: Someone else's recommendation
- **WHEN** user A posts feedback for a recommendation id that belongs to user B
- **THEN** the response is 404 and no event is stored

#### Scenario: No ranking effect
- **WHEN** a user has viewed a recommendation many times
- **THEN** its score and rank in the next generation are the same as without the views

### Requirement: Save recommendations
A user SHALL be able to save and unsave a recommendation's repository (`POST` and `DELETE /api/v1/recommendations/{id}/save`). Saving SHALL be idempotent and store the save time. Every recommendation in the list and detail responses SHALL say whether its repository is saved. A saved repository SHALL stay saved when it is no longer recommended.

#### Scenario: Save and unsave
- **WHEN** a user saves a recommendation, then unsaves it
- **THEN** the recommendation reports `saved: true`, then `saved: false`, and `saved` then `unsaved` events are recorded

#### Scenario: Saving twice
- **WHEN** a user saves an already saved recommendation
- **THEN** the save time is unchanged and no duplicate save exists

### Requirement: Saved projects
The system SHALL provide `GET /api/v1/saved` (paginated, most recently saved first) listing the user's saved repositories, each with the save time, the repository summary, its current activity label, and its current recommendation (id, match label and reasons) or none when it is no longer recommended. `DELETE /api/v1/saved/{repository_id}` SHALL unsave a repository whether or not it is still recommended. The frontend SHALL offer a saved-projects page with these entries; an entry whose repository is no longer recommended SHALL say so rather than implying it is still a good fit.

#### Scenario: Saved but no longer recommended
- **WHEN** a saved repository is not in the user's latest recommendations
- **THEN** it is still listed, with no current recommendation, and the page says it is no longer recommended

### Requirement: Dismiss recommendations
A user SHALL be able to dismiss a recommendation (`POST /api/v1/recommendations/{id}/dismiss`). The recommendation SHALL disappear from the user's list immediately, and its repository SHALL NOT be recommended to that user by any later generation. `GET /api/v1/dismissed` SHALL list dismissed repositories, and `DELETE /api/v1/dismissed/{repository_id}` SHALL restore one, after which it MAY be recommended again by the next generation. Dismissing a saved repository SHALL unsave it.

#### Scenario: Dismissed stays hidden
- **WHEN** a user dismisses a recommendation and recommendations are regenerated
- **THEN** that repository is not among the user's recommendations

#### Scenario: Dismiss during a generation
- **WHEN** a user dismisses a repository while a generation job is running
- **THEN** the job's result does not contain that repository

#### Scenario: Restore
- **WHEN** a user restores a dismissed repository
- **THEN** it is no longer listed as dismissed, an `undismissed` event is recorded, and a new generation is started

### Requirement: Save and dismiss in the interface
Recommendation cards and the detail page SHALL offer Save/Saved and Dismiss actions that update without a page reload. Dismissing SHALL offer an immediate undo. Opening a recommendation's detail page SHALL record a view, and following its GitHub link SHALL record an opened-repository event, without delaying navigation; a failure to record SHALL NOT be shown as an error.

#### Scenario: Save from the card
- **WHEN** the user clicks Save on a card
- **THEN** the button becomes Saved without a reload and the project appears on the saved-projects page

#### Scenario: Dismiss with undo
- **WHEN** the user dismisses a card and then clicks Undo
- **THEN** the card disappears, then the repository is restored and no longer listed as dismissed
