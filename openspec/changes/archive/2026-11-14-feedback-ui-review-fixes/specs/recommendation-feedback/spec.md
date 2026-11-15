## ADDED Requirements

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
