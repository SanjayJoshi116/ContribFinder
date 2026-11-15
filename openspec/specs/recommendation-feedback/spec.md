# recommendation-feedback Specification

## Purpose

Lets developers act on their recommendations (save the ones they want to keep, dismiss the ones they don't) and records their interactions as feedback that is stored independently of the recommendations, for later analytics and evaluation.
## Requirements
### Requirement: Feedback events
The system SHALL record a feedback event for a user's recommendation interactions: `viewed`, `saved`, `unsaved`, `dismissed`, `undismissed`, `opened_repository` and `opened_issue`. Each event SHALL store the user, the repository, the recommendation it came from (when it still exists), the action, the time, and a snapshot of the recommendation's match label, rank and scoring configuration version at that moment. An `opened_issue` event SHALL also store the issue (while it still exists) and a snapshot of its number. A `dismissed` event SHALL also store the dismiss reason when the user gave one. Events SHALL remain intact when the recommendation is regenerated or removed, or when the issue is closed or removed. `POST /api/v1/recommendations/{id}/feedback` SHALL accept `viewed`, `opened_repository` and `opened_issue` for the requesting user's own recommendations; `opened_issue` SHALL require the id of one of that recommendation's relevant issues; an issue of another repository SHALL be rejected with a 400 error, and an issue that is no longer relevant when the event is recorded (closed, or dropped by a regeneration meanwhile) SHALL store no event and SHALL NOT be an error. Saved, dismissed and their reversals SHALL be recorded by the save and dismiss actions themselves. A `viewed` event for the same user and recommendation within the configured window (default 30 minutes) SHALL NOT create a second event, also when the views arrive at the same time. An interaction posted for a recommendation that no longer exists when it is recorded (dropped by a regeneration meanwhile) SHALL store no event and SHALL NOT be an error. Recording an event SHALL NOT wait for a generation job storing its result. Following a repository's or an issue's GitHub link SHALL count whether the link is clicked or opened with the middle mouse button. Feedback SHALL NOT change scores or ranking.

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

#### Scenario: Opened with the middle mouse button
- **WHEN** a user opens a recommendation's GitHub link with the middle mouse button
- **THEN** one `opened_repository` event is recorded, as for a click

### Requirement: Feedback rank snapshot
A feedback event's rank snapshot SHALL be empty when the event had no recommendation, and otherwise a whole number of at least 1; the database SHALL refuse a rank of 0. Upgrading SHALL keep every stored event: an event stored with rank 0 SHALL have its rank emptied, which the feedback report already counts as no rank.

#### Scenario: Rank 0 refused
- **WHEN** any writer stores a feedback event with rank 0
- **THEN** the database refuses the row and nothing is stored

#### Scenario: Event without a recommendation
- **WHEN** a feedback event is stored with no recommendation
- **THEN** its rank is empty and the event is stored

#### Scenario: Upgrade empties a rank 0
- **WHEN** the upgrade runs while an event has rank 0
- **THEN** the event stays stored with an empty rank, and the feedback report counts it as unattributed as before

### Requirement: Save recommendations
A user SHALL be able to save and unsave a recommendation's repository (`POST` and `DELETE /api/v1/recommendations/{id}/save`). Saving SHALL be idempotent and store the save time. Every recommendation in the list and detail responses SHALL say whether its repository is saved. A saved repository SHALL stay saved when it is no longer recommended. Saving a recommendation that no longer exists, or whose repository the user has dismissed, SHALL answer 404 and SHALL store no save and no event, also when the save races a dismiss of the same repository.

#### Scenario: Save and unsave
- **WHEN** a user saves a recommendation, then unsaves it
- **THEN** the recommendation reports `saved: true`, then `saved: false`, and `saved` then `unsaved` events are recorded

#### Scenario: Saving twice
- **WHEN** a user saves an already saved recommendation
- **THEN** the save time is unchanged and no duplicate save exists

#### Scenario: Save racing a dismiss
- **WHEN** a user dismisses a recommendation in one tab while another tab saves the same recommendation
- **THEN** the repository ends dismissed and not saved, and the save either answers 404 or completes before the dismiss removes it

### Requirement: Saved projects
The system SHALL provide `GET /api/v1/saved` (paginated, most recently saved first) listing the user's saved repositories, each with the save time, the repository summary, its current activity label, and its current recommendation (id, match label and reasons) or none when it is no longer recommended. `DELETE /api/v1/saved/{repository_id}` SHALL unsave a repository whether or not it is still recommended. The frontend SHALL offer a saved-projects page with these entries; an entry whose repository is no longer recommended SHALL say so rather than implying it is still a good fit.

#### Scenario: Saved but no longer recommended
- **WHEN** a saved repository is not in the user's latest recommendations
- **THEN** it is still listed, with no current recommendation, and the page says it is no longer recommended

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
Recommendation cards and the detail page SHALL offer Save/Saved and Dismiss actions that update without a page reload. Dismissing SHALL take one action, and the interface SHALL also offer to dismiss with one of the reasons (not my stack, too big, inactive, already know it), operable by keyboard and closable with Escape; giving a reason SHALL be optional. The hidden list SHALL show an entry's reason when it has one. Dismissing SHALL offer an immediate undo, available for 10 seconds from the dismissal; changing filters or the page meanwhile SHALL NOT restart that window. The undo SHALL be offered once per dismissal: reloading the page or returning to it through the browser history SHALL NOT offer it again. Dismissing from the detail page SHALL return to the list page and filters it was opened from. The Save/Saved action SHALL be disabled while a save or unsave request is in flight, so its label always ends matching the stored state. Opening a recommendation's detail page SHALL record a view, and following its GitHub link SHALL record an opened-repository event, without delaying navigation; a failure to record SHALL NOT be shown as an error.

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

#### Scenario: Undo not offered again
- **WHEN** the user dismisses from the detail page, opens another recommendation within 10 seconds and goes Back
- **THEN** the list shows no Undo notice for the earlier dismissal

#### Scenario: Dismiss from the detail page keeps the list's filters
- **WHEN** the user opens a recommendation from page 2 of the Python-filtered list and dismisses it there
- **THEN** page 2 of the Python-filtered list is shown with the Undo notice

### Requirement: Complete saved and hidden lists
The saved-projects page SHALL be able to show every saved and every hidden (dismissed) project,
however many there are. Each list SHALL load one page at a time and offer "Show more" while
further entries exist; "Show more" SHALL be disabled while a page is loading. Removing a saved
project or restoring a hidden one SHALL keep the entries already shown.

`GET /api/v1/saved` and `GET /api/v1/dismissed` SHALL continue each page after the last entry
of the previous one, ordered by save (or dismiss) time and then id, newest first: the `next` link
of a page SHALL carry an opaque `cursor` that marks that entry. A page fetched with a cursor
SHALL contain only entries older than the cursor's entry, so entries added, removed or restored
between two requests SHALL neither repeat an entry already returned nor skip one that existed
throughout. Responses SHALL keep `count` (the total), `next` and `previous`; the lists page
forward only, so `previous` SHALL always be null. A request without a cursor SHALL keep accepting
`page` and `page_size`, and its `next` link SHALL carry a cursor as well. A cursor that cannot be
read SHALL be rejected with a 400 error with code `invalid_cursor`, and a request that sends both
a cursor and a page number SHALL be rejected with a 400 error with code `cursor_with_page`. The
interface SHALL show each entry once.

#### Scenario: More than one page saved
- **WHEN** the user has 130 saved projects and opens the saved-projects page
- **THEN** the first page is listed with "Show more", and selecting it until it disappears lists all 130

#### Scenario: Restore from a later page
- **WHEN** the user has 120 hidden projects, shows them all and restores the last one
- **THEN** it leaves the hidden list, and the other 119 stay listed

#### Scenario: Unsaved in another tab between pages
- **WHEN** the user has 60 saved projects, has the first 50 shown, unsaves one of them in another tab and then selects "Show more"
- **THEN** the next page lists the remaining 10 projects, none of them already shown and none skipped

#### Scenario: Saved in another tab between pages
- **WHEN** the user has the first page of saved projects shown, saves a new project in another tab and then selects "Show more"
- **THEN** the next page starts with the project after the last one shown, not with one already listed

#### Scenario: Unreadable cursor
- **WHEN** a client requests `GET /api/v1/saved?cursor=garbage`
- **THEN** the response is 400 with error code `invalid_cursor`

#### Scenario: Page number without a cursor
- **WHEN** a client requests `GET /api/v1/saved?page=2&page_size=10` and the user has 25 saved projects
- **THEN** the response lists the 11th to 20th most recently saved, `count` is 25, `previous` is null, and `next` carries a cursor that continues with the 21st

#### Scenario: Cursor and page together
- **WHEN** a client requests `GET /api/v1/dismissed?cursor=<a valid cursor>&page=3`
- **THEN** the response is 400 with error code `cursor_with_page`

### Requirement: Failed feedback actions
When a save, unsave, dismiss, remove, restore or "Show more" request fails, the interface SHALL
say so next to the control that started it ("Couldn't save.", "Couldn't hide.", "Couldn't
remove.", "Couldn't restore.", "Couldn't load more.") and SHALL leave the control usable to try
again; the message SHALL disappear when the action is tried again or succeeds. Undoing a failed
optimistic change SHALL revert only the recommendation that action changed: a failure SHALL NOT
undo another action's change to another recommendation, whether that action is still in flight or
already confirmed. Interaction events (views, opened repository, opened issue) SHALL still never
show an error.

#### Scenario: Failed save beside a confirmed dismissal
- **WHEN** the user clicks Save on card A, then Dismiss on card B, the dismissal succeeds and A's save then fails
- **THEN** A shows Save again with "Couldn't save.", and B stays hidden

#### Scenario: Failed removal from the saved page
- **WHEN** the user clicks Remove on a saved project and the request fails
- **THEN** the project stays listed with "Couldn't remove." and Remove can be clicked again

#### Scenario: Failed "Show more"
- **WHEN** loading the next page of hidden projects fails
- **THEN** the entries already shown stay listed, "Couldn't load more." is shown and "Show more" can be clicked again

### Requirement: Undo notice lifecycle
Each dismissal SHALL get its own undo notice: a new dismissal while a notice is shown SHALL
replace it with a notice for the new project, without the previous project's undo state (an
error or a pending restore). An undo in flight SHALL keep the notice open until it settles: a
successful undo SHALL close it, and a failed one SHALL show "Undo didn't work." and keep the
notice open for 10 seconds from the failure, so the user always learns the result. Dismissing
from the detail page SHALL return to the list only while the user is still on that detail page;
once they have gone elsewhere, the confirmed dismissal SHALL NOT navigate.

#### Scenario: Second dismissal after a failed undo
- **WHEN** the user's undo of project A fails and they dismiss project B within 10 seconds
- **THEN** the notice names B, shows no error and B's Undo is enabled

#### Scenario: Slow undo at the end of the window
- **WHEN** the user clicks Undo 9 seconds after a dismissal and the request takes 3 seconds and fails
- **THEN** the notice stays open past 10 seconds and shows "Undo didn't work."

#### Scenario: Leaving the detail page during a dismissal
- **WHEN** the user clicks Dismiss on a detail page and opens the saved-projects page before the request completes
- **THEN** the saved-projects page stays open once the dismissal is confirmed

