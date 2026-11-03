import { describe, expect, it } from 'vitest'

import type { IssueDetail } from '@/api/types'

import { contributionBasis, difficultyBasis } from './evidence'

type Analysis = IssueDetail['analysis']

const analysis = (patch: Record<string, unknown>) =>
  ({
    difficulty: 'beginner',
    difficulty_evidence: { signals: [] },
    contribution_type_evidence: {},
    ...patch,
  }) as unknown as Analysis

describe('difficultyBasis', () => {
  it('leaves out a signal it has no words for', () => {
    const signals = [
      { signal: 'linked_prs', vote: 'beginner', value: 3 },
      { signal: 'body_length', vote: 'beginner', value: 40 },
    ]
    expect(difficultyBasis(analysis({ difficulty_evidence: { signals } }))).toEqual([
      'Short description',
    ])
  })

  it('reads nothing from signals that are not a list', () => {
    expect(difficultyBasis(analysis({ difficulty_evidence: { signals: {} } }))).toEqual([])
    expect(difficultyBasis(analysis({ difficulty_evidence: {} }))).toEqual([])
    expect(difficultyBasis(analysis({ difficulty_evidence: null }))).toEqual([])
    expect(difficultyBasis(analysis({ difficulty_evidence: { signals: [null, 3] } }))).toEqual([])
  })
})

describe('contributionBasis', () => {
  it('names the category of the deciding label', () => {
    expect(
      contributionBasis(
        analysis({ contribution_type_evidence: { by: 'label', value: 'documentation' } }),
      ),
    ).toBe('From a documentation label')
  })

  it('uses "an" before a vowel', () => {
    expect(
      contributionBasis(
        analysis({ contribution_type_evidence: { by: 'label', value: 'enhancement' } }),
      ),
    ).toBe('From an enhancement label')
  })

  it('quotes the title keyword', () => {
    expect(
      contributionBasis(analysis({ contribution_type_evidence: { by: 'keyword', value: 'typo' } })),
    ).toBe('From "typo" in the title')
  })
})
