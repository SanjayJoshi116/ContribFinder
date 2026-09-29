import type { DiscoveryStatus, SyncJob } from '@/api/types'
import { isActive } from '@/features/sync/api'

const FAILURES: Record<string, string> = {
  github_auth_invalid:
    'GitHub access has expired or was revoked. Sign in with GitHub again to find projects.',
  github_rate_limited:
    'GitHub is limiting requests right now. We will look for projects again on your next refresh.',
  github_unavailable:
    'GitHub is not responding right now. We will look for projects again on your next refresh.',
}
const GENERIC_FAILURE = 'Finding projects stopped unexpectedly. Refresh your profile to try again.'

export function discoveryFailure(job: SyncJob): string {
  return FAILURES[job.error_code] ?? GENERIC_FAILURE
}

const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['day', 86_400],
  ['hour', 3_600],
  ['minute', 60],
]

export function timeAgo(iso: string, now: number = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000)
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit)
  }
  return relative.format(0, 'minute')
}

export interface DiscoveryMessage {
  text: string
  alert: boolean
}

/** One line describing the discovery state. Never a score, percentage or ranking. */
export function describeDiscovery(status: DiscoveryStatus, now?: number): DiscoveryMessage {
  const { job, pool, last_completed_at } = status
  if (isActive(job)) return { text: 'Finding projects that match your profile…', alert: false }
  if (job?.status === 'FAILED') return { text: discoveryFailure(job), alert: true }
  if (last_completed_at) {
    const noun = pool.eligible === 1 ? 'candidate project' : 'candidate projects'
    return {
      text: `${pool.eligible} ${noun} found · updated ${timeAgo(last_completed_at, now)}`,
      alert: false,
    }
  }
  return { text: "We'll look for projects after your profile is ready.", alert: false }
}
