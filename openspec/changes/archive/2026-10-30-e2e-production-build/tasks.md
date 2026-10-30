## 1. Production build under Playwright

- [x] 1.1 `vite.config.ts`: one `/api` proxy constant used by `server.proxy` and `preview.proxy`
- [x] 1.2 `playwright.config.ts`: frontend web server runs `vite build --outDir dist-e2e --emptyOutDir` then `vite preview --outDir dist-e2e --port 5174 --strictPort`; `E2E_DEV_SERVER=1` keeps the dev server; timeout covers the build
- [x] 1.3 `apps/frontend/.gitignore` (and ESLint/Prettier ignores, if they list `dist`): add `dist-e2e`

## 2. Policy check

- [x] 2.1 `e2e/fixtures.ts`: auto fixture collecting console errors that mention `Content Security Policy`, failing the test with the collected messages
- [x] 2.2 Every spec still imports `test` from `fixtures.ts` (no direct `@playwright/test` import in a spec)
- [x] 2.3 Verify once by hand: a temporary foreign `<img>` (or `fetch` to another origin) on the dashboard makes `dashboard.spec.ts` fail naming the violation; then remove it

## 3. Checks

- [x] 3.1 `npm run e2e` passes locally against the production build; also with `E2E_DEV_SERVER=1`
- [x] 3.2 `npm run lint`, `npm run format:check`, `npm run typecheck`; root `npm run lint:scripts` if scripts change
- [x] 3.3 CI `e2e` job green on the branch; note its duration against the previous run (green on `main` after the v0.12.38 push, 2026-10-30; CI duration not recorded)

## 4. Docs and release

- [x] 4.1 README "Browser tests": production build by default, `E2E_DEV_SERVER=1` for the dev server; CLAUDE.md §6 `npm run e2e` line
- [x] 4.2 Archive (delta into `web-client`); `ideas.md` moves the §14 production-build item to Shipped
- [x] 4.3 Release housekeeping (CLAUDE.md §8): patch bump, CHANGELOG, features.txt, README, CLAUDE.md entry
