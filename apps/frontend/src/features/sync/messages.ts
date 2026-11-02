import type { SyncJob, SyncStepState } from '@/api/types'

/** A stalled job (its worker stopped): the first sentence of every notice about it. */
export const STALLED_NOTICE =
  'Background work stopped. It resumes automatically within a few minutes'

export const STEP_LABELS: Record<string, string> = {
  profile: 'Profile',
  readme: 'Profile README',
  repositories: 'Repositories',
  languages: 'Languages',
  topics: 'Topics',
  dependencies: 'Dependencies',
  contributions: 'Contributions',
  analysis: 'Building profile',
}
export const STEP_ORDER = [
  'profile',
  'readme',
  'repositories',
  'languages',
  'topics',
  'dependencies',
  'contributions',
  'analysis',
] as const

export const STEP_STATE_LABELS: Record<SyncStepState, string> = {
  pending: 'Waiting',
  running: 'In progress',
  done: 'Done',
  not_found: 'Not found',
  skipped: 'Skipped',
  failed: 'Failed',
}

export interface FailureMessage {
  text: string
  /** Re-authorizing with GitHub is the fix (vs. simply retrying). */
  needsSignIn: boolean
}

const FAILURES: Record<string, FailureMessage> = {
  github_auth_invalid: {
    text: 'GitHub access has expired or was revoked. Sign in with GitHub again to continue.',
    needsSignIn: true,
  },
  github_not_connected: {
    text: 'Your GitHub account is not connected. Sign in with GitHub to continue.',
    needsSignIn: true,
  },
  github_rate_limited: {
    text: 'GitHub is limiting requests right now. Please try again in a few minutes.',
    needsSignIn: false,
  },
  analysis_failed: {
    text: 'Your GitHub data was synced, but your profile could not be built from it. Please try again.',
    needsSignIn: false,
  },
  github_unavailable: {
    text: 'GitHub is not responding right now. Please try again shortly.',
    needsSignIn: false,
  },
}

const GENERIC_FAILURE: FailureMessage = {
  text: 'The sync stopped unexpectedly. Please try again.',
  needsSignIn: false,
}

export function failureMessage(job: SyncJob): FailureMessage {
  if (job.status === 'CANCELLED') return { text: 'The sync was cancelled.', needsSignIn: false }
  return FAILURES[job.error_code] ?? GENERIC_FAILURE
}

export function formatWait(seconds: number): string {
  if (seconds < 60) return `${seconds} second${seconds === 1 ? '' : 's'}`
  const minutes = Math.ceil(seconds / 60)
  return `${minutes} minute${minutes === 1 ? '' : 's'}`
}
