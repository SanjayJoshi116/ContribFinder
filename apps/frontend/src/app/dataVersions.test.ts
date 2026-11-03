import { describe, expect, it } from 'vitest'

import { AREA_KEYS, changedAreas } from './dataVersions'

const BASE = {
  github: '2026-10-27T10:00:00Z',
  profile: '2026-10-27T10:01:00Z',
  recommendations: '2026-10-27T10:03:00Z',
}

describe('changedAreas', () => {
  it.each([
    ['nothing changed', {}, []],
    ['one area newer', { recommendations: '2026-10-27T10:20:00Z' }, ['recommendations']],
    ['an area older (a dismiss)', { recommendations: '2026-10-27T09:00:00Z' }, ['recommendations']],
    ['an area emptied', { profile: null }, ['profile']],
    [
      'every area',
      { github: '2026-10-27T11:00:00Z', profile: '2026-10-27T11:01:00Z', recommendations: null },
      ['github', 'profile', 'recommendations'],
    ],
  ])('%s', (_name, patch, expected) => {
    expect(changedAreas(BASE, { ...BASE, ...patch })).toEqual(expected)
  })

  it('treats a first value after null as a change', () => {
    const empty = { github: null, profile: null, recommendations: null }
    expect(changedAreas(empty, BASE)).toEqual(['github', 'profile', 'recommendations'])
  })
})

describe('AREA_KEYS', () => {
  it('covers the hidden list in recommendations, and never a job status', () => {
    expect(AREA_KEYS.recommendations).toContainEqual(['profile', 'dismissed'])
    const keys = Object.values(AREA_KEYS).flat()
    expect(keys.every((key) => key[0] === 'profile')).toBe(true)
  })
})

/** Every source file except tests and the area table itself, as text (APP-9). */
const SOURCES = import.meta.glob<string>(
  ['/src/**/*.{ts,tsx}', '!/src/**/*.test.{ts,tsx}', '!/src/app/dataVersions.ts'],
  {
    query: '?raw',
    import: 'default',
  },
)

describe('AREA_KEYS coverage', () => {
  it('covers every derived query key under profile', async () => {
    // Read only when this test runs, in parallel.
    const texts = await Promise.all(Object.values(SOURCES).map((load) => load()))
    const names = new Set<string>()
    for (const text of texts) {
      for (const match of text.matchAll(/\['profile',\s*'([^']+)'/g)) names.add(match[1])
    }
    const covered = new Set(
      Object.values(AREA_KEYS)
        .flat()
        .map((key) => key[1]),
    )
    // A refactor that hides the literals must fail here, not pass with nothing to check.
    expect(names.size).toBeGreaterThanOrEqual(covered.size)
    expect([...names].filter((name) => !covered.has(name))).toEqual([])
  })
})
