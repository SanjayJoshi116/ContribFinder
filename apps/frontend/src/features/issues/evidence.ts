import type { DifficultySignal, DifficultyVote, IssueDetail } from '@/api/types'

type Analysis = IssueDetail['analysis']

/** A stored vote: the generated shape, but `signal` may be a name this page does not know. */
type Vote = Omit<DifficultyVote, 'signal'> & { signal: string }

/** Words for each declared difficulty signal (`DifficultySignal` in the API schema): a signal
 * without words fails the type check. The backend test `tests/test_difficulty_signals.py` keeps
 * the declared set equal to what the classifier writes (FI-2). */
const SIGNAL_TEXT: Record<DifficultySignal, (vote: Vote, analysis: Analysis) => string> = {
  label: (s) => `Label "${String(s.value)}"`,
  body_length: (_s, analysis) =>
    analysis.difficulty === 'advanced' ? 'Long description' : 'Short description',
  technology_count: (s) =>
    s.value === 1 ? 'Mentions one technology' : `Mentions ${String(s.value)} technologies`,
  contribution_type: () => 'Documentation work',
  comments: (s) => `Long discussion (${String(s.value)} comments)`,
}

/** Stored evidence may name a signal this page does not know (an older or newer backend). */
function isKnown(signal: unknown): signal is DifficultySignal {
  return typeof signal === 'string' && Object.hasOwn(SIGNAL_TEXT, signal)
}

/** The signals that pointed to the estimated difficulty, in words. */
export function difficultyBasis(analysis: Analysis): string[] {
  // FI-4, CR-4: stored evidence is data, not a promise; anything but a list of objects is skipped.
  const signals: unknown = (analysis.difficulty_evidence as { signals?: unknown } | null)?.signals
  if (!Array.isArray(signals)) return []
  return signals
    .filter((s): s is Vote => typeof s === 'object' && s !== null)
    .flatMap((s) =>
      s.vote === analysis.difficulty && isKnown(s.signal)
        ? [SIGNAL_TEXT[s.signal](s, analysis)]
        : [],
    )
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
