## Context

See proposal.md for why; requirements are in `specs/api-platform` and `specs/web-client`.
- Django 5.2 (`pyproject.toml` pins `<6`) has no built-in CSP (Django 6.0 adds one). Existing
  headers come from `SecurityMiddleware` and `XFrameOptionsMiddleware`.
- DRF renders JSON only (`DEFAULT_RENDERER_CLASSES`); the only HTML Django serves is the admin
  and its error pages. JSON errors come from `config/exceptions.py` and the `core` views.
- The SPA is served by Vite in development (`npm start`, Docker) and has no production host in
  this repository; the build is `vite build` → `dist/`. It loads the avatar from
  `avatars.githubusercontent.com` (`SignedInLayout`); GitHub links are navigations; sign-in is a
  plain link to `/api/v1/auth/github`. Recharts and Radix set `style` attributes; Tailwind's CSS
  is an external file in the build. Vite's build emits module scripts by `src` only.
- `core/checks.py` holds the production checks (`run_startup_checks`).

## Goals / Non-Goals

**Goals:**
- Every Django response carries a CSP; the API's is deny-all.
- The built SPA declares a CSP that the app runs under without violations.

**Non-Goals:**
- Nonces or hashes for inline scripts (none are needed in the build).
- `report-uri` / `report-to` reporting (no endpoint to receive reports; possible later).
- A production web server config for the SPA (none exists here); README describes the header to
  send.
- Upgrading to Django 6 for its built-in CSP.

## Decisions

**D1. A small middleware, `core.csp.ContentSecurityPolicyMiddleware`.**
- Placed right after `SecurityMiddleware`. On the way out it sets the header only when the
  response has none, choosing `CONTENT_SECURITY_POLICY_API` when the `Content-Type` is
  `application/json` (also `application/problem+json`-style suffixes: media type ends with
  `json`) and `CONTENT_SECURITY_POLICY_HTML` otherwise.
- Defaults in `base.py`:
  - API: `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`.
  - HTML: `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline';
    object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`. The admin
    uses a few inline `style` attributes; its scripts are external files.
- *Alternative:* `django-csp`. Rejected: a dependency for two static strings; its nonce machinery
  is not needed.
- *Alternative:* one policy for everything. Rejected: the admin needs `'self'` resources, and the
  API needs nothing.

**D2. Settings plus a production check.**
- Plain settings (not env): changing the policy is a code review, like the other security
  headers. `core.checks` gets a new error id (next free `core.E0xx`) for an empty or non-string
  policy, run by `run_startup_checks` in production and by `manage.py check` everywhere.

**D3. SPA: a build-only Vite plugin that injects the meta tag.**
- `vite.config.ts` adds a plugin with `apply: 'build'` and `transformIndexHtml` that inserts
  `<meta http-equiv="Content-Security-Policy" content="...">` first in `<head>`. The policy string
  lives in one module (`csp.config.ts` next to `vite.config.ts`, imported by the plugin and by a
  Vitest test), so the test checks the same string the build writes.
- Policy: `default-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:
  https://avatars.githubusercontent.com; style-src 'self' 'unsafe-inline'; font-src 'self';
  object-src 'none'; base-uri 'none'; form-action 'self'`. `frame-ancestors` is ignored in a
  meta tag, so it is left out (README: send it as a header).
- *Alternative:* a meta tag in `index.html` for dev too. Rejected: Vite's React refresh preamble
  is an inline script, so dev would need `'unsafe-inline'` scripts and the policy would mean
  nothing.

**D4. Verification of the built app.**
- Vitest: the plugin's output for a sample `index.html` has the meta tag first in `<head>`; the
  policy contains the required directives; `dist/index.html` from a real build has no inline
  `<script>` without `src` (a test over the build output, run after `npm run build` in task 3.x,
  or a check in the build test).
- Manual: `npm run build && npm run preview` (the preview server reuses the `/api` proxy) with
  the backend running; sign in, open the dashboard and a recommendation; the console shows no CSP
  violation.

## Risks / Trade-offs

- [A future dependency adds an inline script or a foreign origin] → It breaks visibly in the
  built app (console error); the manual check and the build test catch inline scripts.
- [`'unsafe-inline'` styles] → Needed for `style` attributes set by Recharts/Radix; scripts stay
  strict, which is where the injection risk is.
- [The meta tag cannot set `frame-ancestors`] → The backend already sends `X-Frame-Options:
  DENY` for its own responses; README tells the SPA's host to send the header.

## Migration Plan

- Deploy; no data change. Rollback: revert the release.
