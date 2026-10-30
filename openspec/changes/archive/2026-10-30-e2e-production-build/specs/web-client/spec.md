## MODIFIED Requirements

### Requirement: End-to-end coverage of the main flows
The project SHALL have browser tests that run the built SPA against the real backend and a real
PostgreSQL database, with data seeded by a command that only the end-to-end configuration
provides. The built SPA SHALL be the production build, served as built with its Content
Security Policy, not the development server; a development-server run MAY be offered for local
use only, and CI SHALL NOT use it. A test SHALL fail when the page reports a Content Security
Policy violation. The production configuration SHALL NOT offer any way to sign in without
GitHub. The tests SHALL make no request to GitHub, and SHALL cover at least:
- the sign-in start redirecting to GitHub with a state;
- a signed-in user without synced data landing on onboarding;
- a synced user's dashboard with profile and recommendations;
- save, then the saved-projects page;
- dismiss and undo;
- following the relevant-issues link to the issues on the detail page;
- an ended session returning to sign-in;
- deleting GitHub data returning to onboarding.

CI SHALL run these tests on every pull request and push to main.

#### Scenario: Seeding outside the end-to-end configuration
- **WHEN** the seed command is invoked under the development, test or production settings
- **THEN** it does not exist there

#### Scenario: CI run
- **WHEN** a pull request is opened
- **THEN** CI runs the browser tests against the production build and fails the build if any of the listed flows fails

#### Scenario: Policy violation fails a test
- **WHEN** a change makes a page load a script, image or connection from an origin the built app's policy does not allow
- **THEN** the browser test that opens that page fails, naming the violation

