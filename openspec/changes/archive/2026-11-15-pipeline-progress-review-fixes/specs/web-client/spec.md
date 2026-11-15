## ADDED Requirements

### Requirement: Pipeline progress display
The dashboard's pipeline stage (syncing, analyzing, finding projects, preparing recommendations,
stalled) SHALL follow the discovery and recommendation statuses whether or not the discovery card
and the recommendation list are shown, for example while the profile is not yet analyzed. A stalled job SHALL NOT be described as progressing anywhere: the discovery card SHALL
show the stalled notice instead of "Finding projects…", and a sync step that is running in a
stalled job SHALL show as stopped, not as an animated "In progress". A step state the interface
does not know SHALL be shown as waiting and SHALL NOT break the page. A relative time ("updated 5
minutes ago") SHALL advance while it is shown, SHALL never be in the future, and SHALL be
formatted in the browser's language like other dates. Every page that shows a GitHub failure code
SHALL use the same reason for it, and a sync start rejected because GitHub is not connected SHALL
offer "Sign in with GitHub again".

#### Scenario: Discovery while the profile is not shown
- **WHEN** the developer profile is not analyzed yet and a discovery run is RUNNING
- **THEN** the dashboard shows "Finding projects…" and polls the discovery status until it finishes

#### Scenario: Stalled discovery card
- **WHEN** the discovery status returns a RUNNING job with `stalled: true`
- **THEN** the discovery card shows the stalled notice, matching the header

#### Scenario: Stalled step
- **WHEN** onboarding shows a stalled sync whose repositories step is running
- **THEN** that step shows as stopped without a spinner, next to the stalled notice

#### Scenario: Unknown step state
- **WHEN** a sync step has a state the interface does not know
- **THEN** that step shows as waiting and the rest of the page renders

#### Scenario: Relative time advances
- **WHEN** the discovery card says "updated this minute" and an hour passes without a new status
- **THEN** it says "updated 1 hour ago"

#### Scenario: Not connected on start
- **WHEN** onboarding's Start sync is answered 409 `github_not_connected`
- **THEN** the page shows the not-connected message and "Sign in with GitHub again"
