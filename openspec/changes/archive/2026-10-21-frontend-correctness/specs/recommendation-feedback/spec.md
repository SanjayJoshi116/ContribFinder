## ADDED Requirements

### Requirement: Complete saved and hidden lists
The saved-projects page SHALL be able to show every saved and every hidden (dismissed) project,
however many there are. Each list SHALL load one page at a time and offer "Show more" while
further entries exist; "Show more" SHALL be disabled while a page is loading. Removing a saved
project or restoring a hidden one SHALL keep the entries already shown.

#### Scenario: More than one page saved
- **WHEN** the user has 130 saved projects and opens the saved-projects page
- **THEN** the first page is listed with "Show more", and selecting it until it disappears lists all 130

#### Scenario: Restore from a later page
- **WHEN** the user has 120 hidden projects, shows them all and restores the last one
- **THEN** it leaves the hidden list, and the other 119 stay listed

## MODIFIED Requirements

### Requirement: Save and dismiss in the interface
Recommendation cards and the detail page SHALL offer Save/Saved and Dismiss actions that update without a page reload. Dismissing SHALL offer an immediate undo, available for 10 seconds from the dismissal; changing filters or the page meanwhile SHALL NOT restart that window. The Save/Saved action SHALL be disabled while a save or unsave request is in flight, so its label always ends matching the stored state. Opening a recommendation's detail page SHALL record a view, and following its GitHub link SHALL record an opened-repository event, without delaying navigation; a failure to record SHALL NOT be shown as an error.

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
