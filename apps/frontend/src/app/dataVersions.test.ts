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
