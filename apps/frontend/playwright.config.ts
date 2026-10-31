import path from 'node:path'

import { defineConfig, devices } from '@playwright/test'

import { SESSIONS_FILE } from './e2e/sessions.ts'

const PORT = 5174
const BASE_URL = `http://localhost:${PORT}`
const VITE = 'node node_modules/vite/bin/vite.js'
const SERVE = `--port ${PORT} --strictPort`
const OUT = '--outDir dist-e2e'
// The production build with its Content Security Policy, in its own folder so a local `dist/`
// stays as it was. Not `npm run build`: that also type-checks (CI's typecheck job) and writes
// `dist/`. The preview listens on localhost only: it proxies to the seeded backend.
// E2E_DEV_SERVER=1 runs the dev server instead (no policy; local use only).
const frontend =
  process.env.E2E_DEV_SERVER === '1'
    ? `${VITE} ${SERVE}`
    : `${VITE} build ${OUT} --emptyOutDir && ${VITE} preview ${OUT} --host localhost ${SERVE}`
const repoRoot = path.resolve(import.meta.dirname, '..', '..')
// The seed builds one user per attempt for tests that change data, so it gets the same number.
const RETRIES = process.env.CI ? 1 : 0

// Browser tests against the real backend and PostgreSQL (database contribfinder_e2e, settings
// config.settings.e2e). Ports 8001 and 5174 keep clear of the `npm start` stack.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: RETRIES,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // Seeds (fresh data on every run), then serves Django.
      command: `node ${JSON.stringify(path.join(repoRoot, 'scripts', 'e2e-backend.mjs'))} ${JSON.stringify(SESSIONS_FILE)} ${RETRIES + 1}`,
      url: 'http://127.0.0.1:8001/api/v1/health/',
      reuseExistingServer: false,
      timeout: 180_000,
      stdout: 'pipe',
    },
    {
      command: frontend,
      url: BASE_URL,
      reuseExistingServer: false,
      // Covers the build; its output shows in the log.
      timeout: 180_000,
      stdout: 'pipe',
      env: { VITE_API_PROXY_TARGET: 'http://127.0.0.1:8001' },
    },
  ],
})
