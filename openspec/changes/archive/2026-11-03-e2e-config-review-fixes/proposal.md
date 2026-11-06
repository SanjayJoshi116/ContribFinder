## Why

The full review sweep of `apps/frontend/e2e/` with `vite.config.ts`, `csp.config.ts` and
`playwright.config.ts` (batch 47 of `Bug_Backlog.md`, E2EC-1…E2EC-7) found browser-test tooling
that breaks in confusing ways under ad-hoc Playwright flags, a dev-server branch that listens on
every interface, a fixture comment that says read-only users write nothing, a Vitest exclude list
that drops Vitest's defaults, and a policy canary that can fail on a duplicate console entry.
None changes what the app does.

## What Changes

- **E2EC-1**: a data-changing test run with `--repeat-each` above 1, or with more retries than the
  seed built users for, fails at sign-in with a message naming the cause and the supported way
  (`RETRIES` in `playwright.config.ts`, a fresh `npm run e2e`), instead of reusing a changed user
  or throwing "attempt N". The config and README say which flags are supported.
- **E2EC-3**: the `E2E_DEV_SERVER=1` dev server listens on localhost only, like the preview.
- **E2EC-4**: the fixture comment says read-only users may record views.
- **E2EC-6**: Vitest's `exclude` extends `configDefaults.exclude` and adds `dist-e2e/**`.
- **E2EC-7**: the canary accepts any number of taken violations as long as each names the
  `img-src` directive.
- No change: **E2EC-2** (dev server on every interface; accepted as hardening, Docker publishes
  5173) and **E2EC-5** (console wording; the canary is the guard).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None (`skip_specs`: test tooling and configuration only; "End-to-end coverage of the main flows"
is unchanged).

## Impact

- `apps/frontend/playwright.config.ts`, `e2e/fixtures.ts`, `e2e/policy.spec.ts`,
  `vite.config.ts`, README "End-to-end tests".
- No app, backend or API change. Verified by `npm run e2e` (the change is in the e2e tooling),
  plus the usual frontend checks.
