/// <reference types="vitest/config" />
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  server: {
    host: true,
    port: 5173,
    // Same-origin in dev: the browser only ever talks to :5173, so session
    // and CSRF cookies work without cross-site configuration.
    proxy: {
      '/api': { target: apiTarget, changeOrigin: false, xfwd: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // Browser tests run under Playwright (`npm run e2e`), not Vitest.
    exclude: ['**/node_modules/**', 'e2e/**'],
    // Room for several findBy* waits (5 s each, see src/test/setup.ts) in one test.
    testTimeout: 15_000,
    css: false,
  },
})
