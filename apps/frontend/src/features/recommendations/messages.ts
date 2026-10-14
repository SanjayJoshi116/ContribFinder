import type { ContributionType, Difficulty, MatchLabel, RecommendationStatus } from '@/api/types'
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

/** Issue analysis is an estimate: "unknown" means the evidence was not enough, not an error. */
export const NOT_ENOUGH_EVIDENCE = 'Not enough evidence'

export const DIFFICULTY_TEXT: Record<Difficulty, string> = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  advanced: 'Advanced',
  unknown: NOT_ENOUGH_EVIDENCE,
}

/** An issue's estimated difficulty in words; "unknown" is a lack of evidence, not an error. */
export function difficultyText(difficulty: Difficulty): string {
  return difficulty === 'unknown'
    ? NOT_ENOUGH_EVIDENCE
    : `${DIFFICULTY_TEXT[difficulty]} (estimated)`
}

export const CONTRIBUTION_TYPE_TEXT: Record<ContributionType, string> = {
  code: 'Code',
  documentation: 'Documentation',
  testing: 'Testing',
  bug_fix: 'Bug fix',
  feature: 'Feature',
  devops: 'DevOps',
  design: 'Design',
  unknown: NOT_ENOUGH_EVIDENCE,
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
// Recommendations with at least one relevant issue of that kind.
export const DIFFICULTY_OPTIONS: Option[] = [
  { value: 'beginner', label: 'Beginner issues' },
  { value: 'intermediate', label: 'Intermediate issues' },
  { value: 'advanced', label: 'Advanced issues' },
  { value: 'unknown', label: 'Issues not yet estimated' },
]
export const CONTRIBUTION_TYPE_OPTIONS: Option[] = Object.entries(CONTRIBUTION_TYPE_TEXT)
  .filter(([value]) => value !== 'unknown')
  .map(([value, label]) => ({ value, label }))

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
