import type { IssueDetail } from '@/api/types'

type Analysis = IssueDetail['analysis']

interface Vote {
  signal: string
  vote: string | null
  value: unknown
}

/** Words for each difficulty signal `services/issues/classify.py` writes (`_vote`). The backend
 * test `tests/test_issue_signal_wording.py` keeps the keys equal to what it writes; a signal
 * without words is left out (FI-2). */
const SIGNAL_TEXT: Record<string, (vote: Vote, analysis: Analysis) => string> = {
  label: (s) => `Label "${String(s.value)}"`,
  body_length: (_s, analysis) =>
    analysis.difficulty === 'advanced' ? 'Long description' : 'Short description',
  technology_count: (s) =>
    s.value === 1 ? 'Mentions one technology' : `Mentions ${String(s.value)} technologies`,
  contribution_type: () => 'Documentation work',
  comments: (s) => `Long discussion (${String(s.value)} comments)`,
}

/** The signals that pointed to the estimated difficulty, in words. */
export function difficultyBasis(analysis: Analysis): string[] {
  // FI-4, CR-4: stored evidence is data, not a promise; anything but a list of objects is skipped.
  const signals: unknown = (analysis.difficulty_evidence as { signals?: unknown } | null)?.signals
  if (!Array.isArray(signals)) return []
  return signals
    .filter((s): s is Vote => typeof s === 'object' && s !== null)
    .filter((s) => s.vote === analysis.difficulty && Object.hasOwn(SIGNAL_TEXT, s.signal))
    .map((s) => SIGNAL_TEXT[s.signal]!(s, analysis))
}

/** What decided the contribution type. A label is named by its category, the canonical name
 * the classifier stores, never quoted as if the issue carried a label of that name (FI-1). */
export function contributionBasis(analysis: Analysis): string | null {
  const evidence = (analysis.contribution_type_evidence ?? {}) as { by?: string; value?: string }
  if (evidence.by === 'label') {
    const article = /^[aeiou]/i.test(evidence.value ?? '') ? 'an' : 'a'
    return `From ${article} ${evidence.value} label`
  }
  if (evidence.by === 'keyword') return `From "${evidence.value}" in the title`
  return null
}
