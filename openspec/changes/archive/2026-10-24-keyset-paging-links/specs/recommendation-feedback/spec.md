## MODIFIED Requirements

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
