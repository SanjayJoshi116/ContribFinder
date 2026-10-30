## Context

`playwright.config.ts` starts two web servers: `scripts/e2e-backend.mjs` (seed, Django on
:8001) and `vite --port 5174 --strictPort` with `VITE_API_PROXY_TARGET`. The CSP meta tag comes
from the build-only plugin in `csp.config.ts` (`apply: 'build'`), so the dev server has none.
`csp.config.test.ts` checks `dist/index.html` text when a build exists, but nothing checks the
policy in a browser. Vite's `preview` reuses `server.proxy` unless `preview.proxy` is set, and
serves `index.html` for unknown paths (`appType: 'spa'`), so deep links like
`/app/recommendations/1` work.

## Goals / Non-Goals

**Goals:** CI's browser tests run the production bundle with its policy; any policy violation
fails a test; local runs keep a quick option.

**Non-Goals:** serving the SPA from Django or a CDN; new browsers or flows; a separate CSP spec
file; changing the policy.

## Decisions

### D1. Build and preview inside Playwright's web server command

```ts
const devServer = process.env.E2E_DEV_SERVER === '1'
command: devServer
  ? 'node node_modules/vite/bin/vite.js --port 5174 --strictPort'
  : 'node node_modules/vite/bin/vite.js build --outDir dist-e2e --emptyOutDir && ' +
    'node node_modules/vite/bin/vite.js preview --outDir dist-e2e --port 5174 --strictPort',
timeout: 180_000,
```

`vite build` only (no `tsc -b`): type checking is CI's `typecheck` job, not the browser tests'.
One command string keeps Playwright's start/stop handling (`&&` runs in its shell on every OS
Playwright supports). Alternative: a `pretest` build step in CI; rejected, local runs would test
a stale or missing build.

### D2. Own output folder

`--outDir dist-e2e` so a local `dist/` (and `csp.config.test.ts`, which reads it) is never
replaced by an e2e run. `dist-e2e` is added to `apps/frontend/.gitignore` and the ESLint/Prettier
ignores if they list `dist`.

### D3. Proxy for preview

`vite.config.ts` gets `preview: { proxy: { '/api': same as server } }` sharing one constant, so
the preview proxy does not depend on Vite's fallback to `server.proxy`. `VITE_API_PROXY_TARGET`
is read at config load, so preview sees :8001 the same way.

### D4. Policy violations fail the test

An auto fixture in `e2e/fixtures.ts` listens to `page.on('console')` for errors whose text
contains `Content Security Policy` (Chromium reports every violation there) and, after the test,
`expect(violations).toEqual([])`. A `securitypolicyviolation` listener via `addInitScript` was
considered; rejected, an init script is itself subject to page policy questions and the console
already carries the directive and URL. Every spec imports `test` from `fixtures.ts`, so all are
covered. Under `E2E_DEV_SERVER=1` there is no policy, so the fixture passes trivially.

## Risks / Trade-offs

- Each local run builds (a few seconds). `E2E_DEV_SERVER=1` is the escape hatch.
- A preview bug that the dev server would not have (or the reverse) can surface; that is the
  point, since preview serves what ships.
- Console text matching depends on Chromium's wording; the fixture is tested once by a temporary
  violation (task 2.3) so a wording change shows up as a failing check, not silence.

## Migration Plan

None. Rollback is a revert of the config files.
