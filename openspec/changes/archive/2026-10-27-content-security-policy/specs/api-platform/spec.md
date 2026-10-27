## ADDED Requirements

### Requirement: Content Security Policy
The system SHALL send a `Content-Security-Policy` header on every response it serves that does not already carry one. A JSON response SHALL get a policy that allows loading nothing and forbids framing, `<base>` and form submission (`default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`). Any other response (the admin, error pages) SHALL get a policy that allows resources only from the same origin, forbids framing, plugins and `<base>`, and allows form submission only to the same origin. Both policies SHALL be configurable; production startup SHALL refuse an empty policy.

#### Scenario: API response
- **WHEN** any API endpoint returns JSON, including an error
- **THEN** the response carries `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`

#### Scenario: Admin page
- **WHEN** a staff user opens an admin page
- **THEN** the response carries the HTML policy, which includes `default-src 'self'` and `frame-ancestors 'none'`, and the page's own scripts and styles load

#### Scenario: Response that sets its own policy
- **WHEN** a view sets a `Content-Security-Policy` header itself
- **THEN** that header is sent unchanged

#### Scenario: Empty policy in production
- **WHEN** production settings set either policy to an empty string
- **THEN** startup fails with a configuration error naming the setting
