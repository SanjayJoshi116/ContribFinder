## MODIFIED Requirements

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

