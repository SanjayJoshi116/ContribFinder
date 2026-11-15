import type { DiscoveryStatus, SyncJob } from '@/api/types'
import { isActive, isStalled } from '@/app/jobTransitions'
import { GITHUB_FAILURES, STALLED_NOTICE } from '@/features/sync/messages'
import { formatRelative } from '@/lib/format'

const GENERIC_FAILURE = 'Finding projects stopped unexpectedly. Refresh your profile to try again.'

/** The shared GitHub reason, then discovery's own next step. */
export function discoveryFailure(job: SyncJob): string {
  const failure = GITHUB_FAILURES[job.error_code]
  if (!failure) return GENERIC_FAILURE
  const next = failure.signIn
    ? `${failure.signIn} to find projects.`
    : 'We will look for projects again on your next refresh.'
  return `${failure.reason} ${next}`
}

export interface DiscoveryMessage {
  text: string
  alert: boolean
}

/** One line describing the discovery state. Never a score, percentage or ranking. */
export function describeDiscovery(status: DiscoveryStatus, now?: number): DiscoveryMessage {
  const { job, pool, last_completed_at } = status
  // Stalled before active: a stopped worker is not progressing (matches the header).
  if (isStalled(job)) return { text: `${STALLED_NOTICE}, or press Refresh.`, alert: false }
  if (isActive(job)) return { text: 'Finding projects that match your profile…', alert: false }
  if (job?.status === 'FAILED') return { text: discoveryFailure(job), alert: true }
  if (last_completed_at) {
    const noun = pool.eligible === 1 ? 'candidate project' : 'candidate projects'
    return {
      text: `${pool.eligible} ${noun} found · updated ${formatRelative(last_completed_at, now)}`,
      alert: false,
    }
  }
  return { text: "We'll look for projects after your profile is ready.", alert: false }
}
