import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { configDefaults } from 'vitest/config'

import { contentSecurityPolicy } from './csp.config.ts'

const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'
// Same-origin: the browser only ever talks to the Vite server, so session and CSRF cookies
// work without cross-site configuration. Shared by the dev server and `vite preview`.
const proxy = { '/api': { target: apiTarget, changeOrigin: false, xfwd: true } }

export default defineConfig({
  plugins: [react(), tailwindcss(), contentSecurityPolicy()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  server: {
    host: true,
    port: 5173,
    proxy,
  },
  preview: { proxy },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // Browser tests run under Playwright (`npm run e2e`), not Vitest.
    // Vitest's own defaults stay (E2EC-6); dist-e2e holds the browser-test build.
    exclude: [...configDefaults.exclude, 'e2e/**', 'dist-e2e/**'],
    // Room for several findBy* waits (5 s each, see src/test/setup.ts) in one test.
    testTimeout: 15_000,
    css: false,
  },
})
