## Why

Neither the backend nor the SPA sends a Content-Security-Policy. Django sets nosniff,
`X-Frame-Options`, a referrer policy and COOP (`config/settings/base.py`), but nothing limits
where a page may load scripts, styles, images or connections from. ContribFinder renders text
that comes from GitHub (README excerpts, issue titles, repository descriptions); React escapes it,
and README excerpts are rendered as text, so a CSP is defense in depth: if an injection ever
slips through, the browser still refuses inline or foreign scripts. `ideas.md` §5
"Content-Security-Policy" is the next platform item in the "can ship now" order (CLAUDE.md §7).
No ranking change.

## What Changes

- Backend: a middleware in `core/` adds a `Content-Security-Policy` header to every Django
  response that has none. JSON responses (the API) get a deny-all policy
  (`default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`); HTML
  responses (the admin, Django's error pages) get a same-origin policy with `frame-ancestors
  'none'`. Both policies are settings (`CONTENT_SECURITY_POLICY_API`,
  `CONTENT_SECURITY_POLICY_HTML`) with these defaults; production startup checks refuse an empty
  value.
- SPA: the production build writes a `<meta http-equiv="Content-Security-Policy">` into
  `index.html`: scripts and connections from the same origin only, images from the same origin,
  `data:` and GitHub avatars (`https://avatars.githubusercontent.com`), styles from the same
  origin plus inline style attributes (Recharts and Radix set them), no objects, no `<base>`.
  The dev server keeps working without it (Vite's hot reload injects inline scripts).
- Whoever serves the built SPA in production can send the same policy as a header; README says
  so (a header also allows `frame-ancestors`, which a meta tag cannot set).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-platform`: new requirement "Content Security Policy" (backend responses).
- `web-client`: new requirement "Content Security Policy in the built app".

## Impact

- Backend: `core/csp.py` (middleware), `config/settings/base.py` (settings, `MIDDLEWARE`),
  `core/checks.py` (non-empty strings in production); tests. No migration, no API schema change.
- Frontend: `vite.config.ts` (build-only plugin), `src/app/csp.ts` (the policy string, shared by
  the plugin and its test) or equivalent; tests. No runtime code change.
- Docs: README (security headers, serving the build), `ideas.md` §5 to "Shipped", CLAUDE.md §7
  shipped entry, CHANGELOG, `features.txt`. Release: patch 0.12.30.
