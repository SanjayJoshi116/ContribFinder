## ADDED Requirements

### Requirement: Render failures and dead ends
An error while rendering a signed-in page SHALL show a page that says something went wrong and
offers to reload and a way back to the dashboard, never the router's default error screen. A
stored time the browser cannot read SHALL be shown as "Unknown" and SHALL NOT break the page.
A page that cannot show what was asked for (a recommendation or issue that no longer exists, or a
first load that failed) SHALL have a heading, SHALL move keyboard focus to it when it replaces
content during a visit, and, for a failed load, SHALL offer to try the load again. While a first
load that failed is being retried, the page SHALL show that it is loading, not the failure
message. Returning to a page through the browser history SHALL NOT scroll to or focus the URL's
section again when that page already did so for that history entry; opening or reloading a link
with a section SHALL still scroll to it. A detail value SHALL wrap instead of widening the page.

#### Scenario: Unreadable time
- **WHEN** a saved project's save time is not a valid time
- **THEN** the saved page shows the project with the time "Unknown"

#### Scenario: Render error
- **WHEN** a component on the dashboard throws while rendering
- **THEN** the page says something went wrong and offers Reload and the way back to the dashboard

#### Scenario: Recommendation gone during a visit
- **WHEN** the user has focused Save on a recommendation page and a refetch answers 404
- **THEN** the page shows the "no longer exists" heading with keyboard focus on it

#### Scenario: Retry after a failed first load
- **WHEN** a recommendation page's first load failed and the user chooses Try again
- **THEN** the page shows that it is loading, then the recommendation when the load succeeds

#### Scenario: Back to a section link
- **WHEN** the user opened `/app/recommendations/5#relevant-issues`, scrolled to the top, opened an issue and went Back
- **THEN** the recommendation page does not scroll to or focus the relevant issues again
