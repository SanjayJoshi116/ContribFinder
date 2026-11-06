import { readFileSync } from 'node:fs'

import { test as base, expect, type TestInfo } from '@playwright/test'

import { SESSIONS_FILE } from './sessions.ts'

/** Users created by `e2e_seed` (apps/backend/e2e). Tests that change data each own one of
 * `e2e-save`, `e2e-dismiss`, `e2e-delete`; the others only read (opening a detail page records
 * a view, E2EC-4). */
export type SeededUser =
  'e2e-dashboard' | 'e2e-unsynced' | 'e2e-save' | 'e2e-dismiss' | 'e2e-delete'

// Written by the seed after this module loads (the backend web server), so read on first use.
let sessions: Record<string, string | string[]> | undefined

/** The session for this attempt. A user that tests change maps to one session per attempt (a
 * retry signs in as a copy the first attempt never touched); the rest map to one shared id.
 * `--repeat-each` and CLI `--retries` past the seeded copies fail here with the reason (E2EC-1).
 * A second run inside one `--ui` session cannot be told apart (same attempt numbers, servers
 * not re-seeded): it reuses changed data and fails on the test's own assertions (CR3-2). */
function sessionId(user: SeededUser, { retry, repeatEachIndex }: TestInfo): string {
  sessions ??= JSON.parse(readFileSync(SESSIONS_FILE, 'utf-8')) as Record<string, string | string[]>
  const ids = sessions[user]
  if (!ids) throw new Error(`No seeded session for ${user}; did the backend seed run?`)
  if (typeof ids === 'string') return ids
  if (repeatEachIndex > 0) {
    throw new Error(
      `--repeat-each is not supported for ${user}: it changes data, and each attempt needs a ` +
        'fresh seeded copy. Run npm run e2e again instead.',
    )
  }
  const id = ids[retry]
  if (!id) {
    throw new Error(
      `No seeded session for ${user}, attempt ${retry + 1}: the seed built ${ids.length}. ` +
        'Set RETRIES in playwright.config.ts (CLI --retries is not supported).',
    )
  }
  return id
}

/** Content Security Policy violations seen so far; `take()` returns and clears them, for a
 * test that causes one on purpose. A later entry with the same text as a taken one (Chromium
 * may log a blocked load twice) is ignored, so it cannot fail the teardown (CR3-1). */
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
      const taken = new Set<string>()
      context.on('console', (message) => {
        const text = message.text()
        if (message.type() !== 'error' || !text.includes('Content Security Policy')) return
        if (!taken.has(text)) seen.push(text)
      })
      await use({
        get seen() {
          return seen
        },
        take() {
          const result = seen
          seen = []
          for (const text of result) taken.add(text)
          return result
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
          value: sessionId(user, testInfo),
          url: baseURL!,
          httpOnly: true,
          sameSite: 'Lax',
        },
      ])
    })
  },
})

export { expect }
