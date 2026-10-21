import path from 'node:path'

import { defineConfig, devices } from '@playwright/test'

import { SESSIONS_FILE } from './e2e/sessions.ts'

const BASE_URL = 'http://localhost:5174'
const repoRoot = path.resolve(import.meta.dirname, '..', '..')

// Browser tests against the real backend and PostgreSQL (database contribfinder_e2e, settings
// config.settings.e2e). Ports 8001 and 5174 keep clear of the `npm start` stack.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // Seeds (fresh data on every run), then serves Django.
      command: `node ${JSON.stringify(path.join(repoRoot, 'scripts', 'e2e-backend.mjs'))} ${JSON.stringify(SESSIONS_FILE)}`,
      url: 'http://127.0.0.1:8001/api/v1/health/',
      reuseExistingServer: false,
      timeout: 180_000,
      stdout: 'pipe',
    },
    {
      command: 'node node_modules/vite/bin/vite.js --port 5174 --strictPort',
      url: BASE_URL,
      reuseExistingServer: false,
      env: { VITE_API_PROXY_TARGET: 'http://127.0.0.1:8001' },
    },
  ],
})
