import type { IssueDetail } from '@/api/types'

type Analysis = IssueDetail['analysis']

interface Vote {
  signal: string
  vote: string | null
  value: unknown
}

/** The signals that pointed to the estimated difficulty, in words. */
export function difficultyBasis(analysis: Analysis): string[] {
  const signals = (analysis.difficulty_evidence.signals ?? []) as Vote[]
  return signals
    .filter((s) => s.vote === analysis.difficulty)
    .map((s) => {
      switch (s.signal) {
        case 'label':
          return `Label "${String(s.value)}"`
        case 'body_length':
          return analysis.difficulty === 'advanced' ? 'Long description' : 'Short description'
        case 'technology_count':
          return s.value === 1
            ? 'Mentions one technology'
            : `Mentions ${String(s.value)} technologies`
        case 'contribution_type':
          return 'Documentation work'
        case 'comments':
          return `Long discussion (${String(s.value)} comments)`
        default:
          return s.signal
      }
    })
}

export function contributionBasis(analysis: Analysis): string | null {
  const evidence = analysis.contribution_type_evidence as { by?: string; value?: string }
  if (evidence.by === 'label') return `From the "${evidence.value}" label`
  if (evidence.by === 'keyword') return `From "${evidence.value}" in the title`
  return null
}
