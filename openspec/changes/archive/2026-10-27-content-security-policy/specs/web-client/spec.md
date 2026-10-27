## ADDED Requirements

### Requirement: Content Security Policy in the built app
The production build of the SPA SHALL declare a Content Security Policy in its `index.html` that allows scripts and network connections only from the same origin, images only from the same origin, `data:` URLs and GitHub avatars (`https://avatars.githubusercontent.com`), styles from the same origin and inline style attributes, and SHALL forbid plugins (`object-src 'none'`) and `<base>` (`base-uri 'none'`). The built app SHALL work under it without policy violations. The development server SHALL NOT add the policy.

#### Scenario: Built index
- **WHEN** the SPA is built for production
- **THEN** `dist/index.html` contains a `Content-Security-Policy` meta tag with `script-src 'self'`, `connect-src 'self'`, `object-src 'none'` and `base-uri 'none'`, and no inline script

#### Scenario: Dashboard under the policy
- **WHEN** a signed-in user opens the dashboard of the built app, with its avatar, language chart and recommendations
- **THEN** every resource loads and the browser reports no Content Security Policy violation

#### Scenario: Development server
- **WHEN** the SPA runs on the Vite development server
- **THEN** `index.html` carries no Content Security Policy and hot reload works
