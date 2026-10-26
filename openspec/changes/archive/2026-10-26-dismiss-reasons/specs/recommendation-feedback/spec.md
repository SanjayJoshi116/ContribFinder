## MODIFIED Requirements

### Requirement: Feedback events
The system SHALL record a feedback event for a user's recommendation interactions: `viewed`, `saved`, `unsaved`, `dismissed`, `undismissed`, `opened_repository` and `opened_issue`. Each event SHALL store the user, the repository, the recommendation it came from (when it still exists), the action, the time, and a snapshot of the recommendation's match label, rank and scoring configuration version at that moment. An `opened_issue` event SHALL also store the issue (while it still exists) and a snapshot of its number. A `dismissed` event SHALL also store the dismiss reason when the user gave one. Events SHALL remain intact when the recommendation is regenerated or removed, or when the issue is closed or removed. `POST /api/v1/recommendations/{id}/feedback` SHALL accept `viewed`, `opened_repository` and `opened_issue` for the requesting user's own recommendations; `opened_issue` SHALL require the id of one of that recommendation's relevant issues and SHALL be rejected with a 400 error otherwise. Saved, dismissed and their reversals SHALL be recorded by the save and dismiss actions themselves. A `viewed` event for the same user and recommendation within the configured window (default 30 minutes) SHALL NOT create a second event, also when the views arrive at the same time. An interaction posted for a recommendation that no longer exists when it is recorded (dropped by a regeneration meanwhile) SHALL store no event and SHALL NOT be an error. Recording an event SHALL NOT wait for a generation job storing its result. Feedback SHALL NOT change scores or ranking.

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

#### Scenario: Simultaneous views
- **WHEN** two requests record a view of the same recommendation at the same time
- **THEN** one `viewed` event exists

### Requirement: Dismiss recommendations
A user SHALL be able to dismiss a recommendation (`POST /api/v1/recommendations/{id}/dismiss`). The recommendation SHALL disappear from the user's list immediately, and its repository SHALL NOT be recommended to that user by any later generation. The dismiss request MAY carry a reason, one of `not_my_stack`, `too_big`, `inactive` and `already_know`; a dismiss without one SHALL behave as before, and an unknown reason SHALL be rejected with a 400 error and change nothing. The reason SHALL be stored with the dismissal and its `dismissed` event, and SHALL never affect scoring or ranking. `GET /api/v1/dismissed` SHALL list dismissed repositories, each with its reason or none, and `DELETE /api/v1/dismissed/{repository_id}` SHALL restore one, after which it MAY be recommended again by the next generation. Dismissing a saved repository SHALL unsave it and record an `unsaved` event. A dismiss of a recommendation that a regeneration dropped meanwhile SHALL still dismiss the repository; its events then reference no recommendation. Save, unsave, dismiss and restore SHALL complete without a server error while a generation job for the same user is storing its result.

#### Scenario: Dismissed stays hidden
- **WHEN** a user dismisses a recommendation and recommendations are regenerated
- **THEN** that repository is not among the user's recommendations

#### Scenario: Dismiss during a generation
- **WHEN** a user dismisses a repository while a generation job is running
- **THEN** the job's result does not contain that repository

#### Scenario: Restore
- **WHEN** a user restores a dismissed repository
- **THEN** it is no longer listed as dismissed, an `undismissed` event is recorded, and a new generation is started

#### Scenario: Dismiss a saved repository
- **WHEN** a user dismisses a recommendation whose repository is saved
- **THEN** the repository is no longer saved, and `dismissed` and `unsaved` events are recorded

#### Scenario: Dismiss while a generation stores its result
- **WHEN** a user dismisses a recommendation at the moment their generation job stores its result
- **THEN** the dismiss succeeds, the generation completes, and the repository is not among the user's recommendations

#### Scenario: Dismiss with a reason
- **WHEN** a user dismisses a recommendation with the reason `inactive`
- **THEN** it is dismissed as without a reason, its `dismissed` event and its hidden entry carry `inactive`, and the next generation's scores are the same as for a dismissal without a reason

#### Scenario: Unknown reason
- **WHEN** a user dismisses a recommendation with the reason `boring`
- **THEN** the response is 400 and the recommendation is not dismissed

### Requirement: Save and dismiss in the interface
Recommendation cards and the detail page SHALL offer Save/Saved and Dismiss actions that update without a page reload. Dismissing SHALL take one action, and the interface SHALL also offer to dismiss with one of the reasons (not my stack, too big, inactive, already know it), operable by keyboard and closable with Escape; giving a reason SHALL be optional. The hidden list SHALL show an entry's reason when it has one. Dismissing SHALL offer an immediate undo, available for 10 seconds from the dismissal; changing filters or the page meanwhile SHALL NOT restart that window. The Save/Saved action SHALL be disabled while a save or unsave request is in flight, so its label always ends matching the stored state. Opening a recommendation's detail page SHALL record a view, and following its GitHub link SHALL record an opened-repository event, without delaying navigation; a failure to record SHALL NOT be shown as an error.

#### Scenario: Save from the card
- **WHEN** the user clicks Save on a card
- **THEN** the button becomes Saved without a reload and the project appears on the saved-projects page

#### Scenario: Dismiss with undo
- **WHEN** the user dismisses a card and then clicks Undo
- **THEN** the card disappears, then the repository is restored and no longer listed as dismissed

#### Scenario: Double click on Save
- **WHEN** the user double-clicks Save on a card
- **THEN** one save request is sent, and the button shows Saved once it completes

#### Scenario: Filter change during Undo
- **WHEN** the user dismisses a card, changes a filter 6 seconds later, and waits
- **THEN** the Undo notice closes 10 seconds after the dismissal, not 10 seconds after the filter change

#### Scenario: Dismiss with a reason from the card
- **WHEN** the user opens the reasons on a card and chooses "Too big"
- **THEN** the card disappears with the same undo as a plain dismissal, and the hidden list shows the project with the reason "Too big"

#### Scenario: Plain dismiss stays one click
- **WHEN** the user clicks Dismiss on a card
- **THEN** the card is dismissed without a reason and without any further question
