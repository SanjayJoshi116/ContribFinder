import { readFileSync } from 'node:fs'

import { test as base, expect } from '@playwright/test'

import { SESSIONS_FILE } from './sessions.ts'

/** Users created by `e2e_seed` (apps/backend/e2e). Tests that change data each own one of
 * `e2e-save`, `e2e-dismiss`, `e2e-delete`; the others are only read. */
export type SeededUser =
  'e2e-dashboard' | 'e2e-unsynced' | 'e2e-save' | 'e2e-dismiss' | 'e2e-delete'

// Written by the seed after this module loads (the backend web server), so read on first use.
let sessions: Record<string, string | string[]> | undefined

/** The session for this attempt. A user that tests change maps to one session per attempt (a
 * retry signs in as a copy the first attempt never touched); the rest map to one shared id. */
function sessionId(user: SeededUser, retry: number): string {
  sessions ??= JSON.parse(readFileSync(SESSIONS_FILE, 'utf-8')) as Record<string, string | string[]>
  const ids = sessions[user]
  if (!ids) throw new Error(`No seeded session for ${user}; did the backend seed run?`)
  const id = typeof ids === 'string' ? ids : ids[retry]
  if (!id) throw new Error(`No seeded session for ${user}, attempt ${retry + 1} (seed --attempts)`)
  return id
}

/** Content Security Policy violations seen so far; `take()` returns and clears them, for a
 * test that causes one on purpose. */
export type PolicyViolations = { readonly seen: readonly string[]; take(): string[] }

export const test = base.extend<{
  signInAs: (user: SeededUser) => Promise<void>
  policyViolations: PolicyViolations
}>({
  // Fails the test on any CSP violation in its context (Chromium logs each as a console
  // error); `policy.spec.ts` guards the wording.
  policyViolations: [
    async ({ context }, use) => {
      let seen: string[] = []
      context.on('console', (message) => {
        if (message.type() === 'error' && message.text().includes('Content Security Policy')) {
          seen.push(message.text())
        }
      })
      await use({
        get seen() {
          return seen
        },
        take() {
          const taken = seen
          seen = []
          return taken
        },
      })
      expect(seen, 'Content Security Policy violations').toEqual([])
    },
    { auto: true },
  ],
  signInAs: async ({ context, baseURL }, use, testInfo) => {
    await use(async (user) => {
      await context.addCookies([
        {
          name: 'sessionid',
          value: sessionId(user, testInfo.retry),
          url: baseURL!,
          httpOnly: true,
          sameSite: 'Lax',
        },
      ])
    })
  },
})

export { expect }
