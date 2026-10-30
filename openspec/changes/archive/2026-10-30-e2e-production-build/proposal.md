## Why

`web-client` says the browser tests run "the built SPA", but Playwright starts the Vite dev
server (`playwright.config.ts`). The dev server adds no Content Security Policy, serves
unbundled modules and skips `lazyLoaders` chunking, so CI never sees what ships: a new script,
image or API origin missing from `csp.config.ts` breaks the built app while every test stays
green (CLAUDE.md, 0.12.30). Testing `vite build` + `vite preview` closes that gap and loads
faster per page (`ideas.md` §14).

## What Changes

- Playwright's frontend web server runs `vite build` then `vite preview --port 5174
  --strictPort` (same port, same `/api` proxy to :8001). `E2E_DEV_SERVER=1` keeps the dev server
  for fast local iteration; CI never sets it.
- A Playwright auto fixture fails a test on any Content Security Policy violation reported by
  the page.
- The e2e build goes to its own `outDir` (`dist-e2e`, gitignored) so it never replaces a local
  `dist/`.
- CI's `e2e` job is unchanged apart from what `npm run e2e` now does.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-client`: "End-to-end coverage of the main flows" states the production build and the
  policy check, which also makes the existing "Dashboard under the policy" scenario of "Content
  Security Policy in the built app" an automated test.

## Impact

- `apps/frontend/playwright.config.ts`, `apps/frontend/e2e/fixtures.ts`, `vite.config.ts`
  (`preview` block), `apps/frontend/.gitignore`, README (browser tests section).
- No backend, API or dependency change. Local `npm run e2e` gains one build (seconds).
