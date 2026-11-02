## MODIFIED Requirements

### Requirement: Ended session returns to sign-in
When any API request answers 401 while the user is signed in to the SPA, the SPA SHALL discard
all cached user data and go to the sign-in page. This SHALL include a refresh of the signed-in
user's identity that answers 401 after it had succeeded. The sign-in page SHALL then say that the
session ended and ask the user to sign in again. A 401 on the sign-in page itself (the normal
signed-out state) SHALL NOT show that notice. A failed refresh of the identity that is not a 401
SHALL NOT replace the signed-in pages while an identity is known.

#### Scenario: Session expired while on the dashboard
- **WHEN** the session expires and the next request from the dashboard answers 401
- **THEN** the user is on the sign-in page with a notice that the session ended, and no cached profile data remains

#### Scenario: Session ended during a mutation
- **WHEN** the user clicks Save and the request answers 401
- **THEN** the user is on the sign-in page with the same notice

#### Scenario: Visiting signed out
- **WHEN** a signed-out visitor opens the sign-in page
- **THEN** no session-ended notice is shown

#### Scenario: Identity refresh answers 401
- **WHEN** the signed-in user's identity is refreshed and the request answers 401
- **THEN** the user is on the sign-in page with the session-ended notice

#### Scenario: Identity refresh fails for a moment
- **WHEN** the signed-in user's identity is refreshed and the request fails with 503 after its retries
- **THEN** the signed-in page stays as it was

## ADDED Requirements

### Requirement: Leaving the signed-in app
After the user logs out, disconnects GitHub or deletes their account, the SPA SHALL go to the
sign-in page without the session-ended notice and SHALL keep no cached user data. After the user
deletes their GitHub data, the SPA SHALL go to onboarding. Only one of these four actions SHALL
be in progress at a time: while one is pending, the others SHALL be unavailable. The sign-in page
SHALL show only its own messages for a sign-in error code; an unknown code SHALL show the
generic sign-in failure message.

#### Scenario: Log out
- **WHEN** a signed-in user logs out
- **THEN** the user is on the sign-in page with no notice, and no profile, recommendation or job data remains cached

#### Scenario: Delete GitHub data
- **WHEN** the user confirms "Delete GitHub data" and the request succeeds
- **THEN** the user is on the onboarding page

#### Scenario: One account action at a time
- **WHEN** "Delete account" is pending
- **THEN** "Delete GitHub data" and "Disconnect GitHub" cannot be started

#### Scenario: Unknown sign-in error code
- **WHEN** a visitor opens `/?auth_error=__proto__`
- **THEN** the sign-in page shows the generic sign-in failure message
