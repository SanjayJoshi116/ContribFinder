import { readFileSync } from 'node:fs'

import { test as base, expect } from '@playwright/test'

import { SESSIONS_FILE } from './sessions.ts'

/** Users created by `e2e_seed` (apps/backend/e2e). Tests that change data own a user. */
export type SeededUser = 'e2e-dashboard' | 'e2e-delete' | 'e2e-unsynced'

function sessionId(user: SeededUser): string {
  const sessions = JSON.parse(readFileSync(SESSIONS_FILE, 'utf-8')) as Record<string, string>
  const id = sessions[user]
  if (!id) throw new Error(`No seeded session for ${user}; did the backend seed run?`)
  return id
}

export const test = base.extend<{ signInAs: (user: SeededUser) => Promise<void> }>({
  signInAs: async ({ context, baseURL }, use) => {
    await use(async (user) => {
      await context.addCookies([
        {
          name: 'sessionid',
          value: sessionId(user),
          url: baseURL!,
          httpOnly: true,
          sameSite: 'Lax',
        },
      ])
    })
  },
})

export { expect }
