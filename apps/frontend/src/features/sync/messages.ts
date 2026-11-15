import type { ApiError } from '@/api/client'
import type { SyncJob, SyncStepState } from '@/api/types'
import { formatDateTime, formatTime } from '@/lib/format'

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

export interface GitHubFailure {
  reason: string
  /** The sign-in that fixes it, when re-authorizing with GitHub is the fix. */
  signIn?: string
}

/** The one reason per GitHub failure code, used by every page that shows one. Each page adds
 * its own next step. */
export const GITHUB_FAILURES: Record<string, GitHubFailure> = {
  github_auth_invalid: {
    reason: 'GitHub access has expired or was revoked.',
    signIn: 'Sign in with GitHub again',
  },
  github_not_connected: {
    reason: 'Your GitHub account is not connected.',
    signIn: 'Sign in with GitHub',
  },
  github_rate_limited: { reason: 'GitHub is limiting requests right now.' },
  github_unavailable: { reason: 'GitHub is not responding right now.' },
}

/** Whether an error code (a failed job's or a rejected start's) is fixed by signing in. */
export function needsSignIn(code: string | undefined): boolean {
  return !!code && !!GITHUB_FAILURES[code]?.signIn
}

const SYNC_RETRY: Record<string, string> = {
  github_rate_limited: 'Please try again in a few minutes.',
  github_unavailable: 'Please try again shortly.',
}

const FAILURES: Record<string, FailureMessage> = {
  ...Object.fromEntries(
    Object.entries(GITHUB_FAILURES).map(([code, { reason, signIn }]) => [
      code,
      {
        text: `${reason} ${signIn ? `${signIn} to continue.` : (SYNC_RETRY[code] ?? 'Please try again.')}`,
        needsSignIn: !!signIn,
      },
    ]),
  ),
  analysis_failed: {
    text: 'Your GitHub data was synced, but your profile could not be built from it. Please try again.',
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

/** The message for a failed sync start, the same on the dashboard and onboarding (ROUTE-5).
 * A cooldown names the clock time from `at` (when the start was sent, close to the rejection),
 * so the text stays true while it is shown (ROUTE-6). */
export function startErrorText(error: ApiError, at: number): string {
  if (error.code === 'sync_cooldown' && error.retryAfter) {
    const when = new Date(at + error.retryAfter * 1000)
    const sameDay = when.toDateString() === new Date(at).toDateString()
    const time = sameDay ? formatTime(when) : formatDateTime(when)
    return `Your data was synced recently. You can refresh again after ${time}.`
  }
  return error.message
}
