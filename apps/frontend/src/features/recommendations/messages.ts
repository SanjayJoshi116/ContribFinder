import type { MatchLabel, RecommendationStatus } from '@/api/types'
import { isActive } from '@/features/sync/api'

/** What users see instead of a score: a label backed by reasons. Never a percentage. */
export const MATCH_TEXT: Record<MatchLabel, string> = {
  strong: 'Strong match',
  good: 'Good match',
  partial: 'Partial match',
}

/** Observable signals, never a health verdict. */
export const ACTIVITY_TEXT: Record<string, string> = {
  recently_active: 'Recently active',
  moderately_active: 'Moderately active',
  low_activity: 'Low recent activity',
}

export const SIZE_TEXT: Record<string, string> = {
  small: 'Small project',
  medium: 'Medium project',
  large: 'Large project',
  unknown: 'Size unknown',
}

export interface Option {
  value: string
  label: string
}

// SRS-2 §55 filter lists, as catalog language names and skill slugs.
export const LANGUAGE_OPTIONS: Option[] = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'go', label: 'Go' },
  { value: 'rust', label: 'Rust' },
  { value: 'java', label: 'Java' },
  { value: 'c++', label: 'C++' },
]
export const FRAMEWORK_OPTIONS: Option[] = [
  { value: 'django', label: 'Django' },
  { value: 'react', label: 'React' },
  { value: 'nextjs', label: 'Next.js' },
  { value: 'fastapi', label: 'FastAPI' },
  { value: 'vue', label: 'Vue' },
  { value: 'spring', label: 'Spring' },
]
export const ACTIVITY_OPTIONS: Option[] = Object.entries(ACTIVITY_TEXT).map(([value, label]) => ({
  value,
  label,
}))
export const SIZE_OPTIONS: Option[] = [
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
]
export const MATCH_OPTIONS: Option[] = Object.entries(MATCH_TEXT).map(([value, label]) => ({
  value,
  label,
}))

/** Why the list is empty, or null when there is nothing to explain. */
export function emptyReason(status: RecommendationStatus | undefined, filtered: boolean): string {
  if (filtered) return 'No recommendations match these filters.'
  if (!status || (!status.job && !status.last_generated_at)) {
    return 'Recommendations appear here once project discovery has finished.'
  }
  if (status.job?.status === 'FAILED') {
    return 'Preparing recommendations stopped unexpectedly. Refresh your profile to try again.'
  }
  return 'No suitable projects yet. They appear as more candidate projects are analyzed.'
}

export function isGenerating(status: RecommendationStatus | undefined): boolean {
  return isActive(status?.job)
}
