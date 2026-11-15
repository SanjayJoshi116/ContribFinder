import { Check, Circle, CircleSlash, LoaderCircle, X } from 'lucide-react'

import type { SyncJob, SyncStepState } from '@/api/types'
import { cn } from '@/lib/utils'

import { STEP_LABELS, STEP_ORDER, STEP_STATE_LABELS } from './messages'

const ICONS: Record<SyncStepState, typeof Check> = {
  pending: Circle,
  running: LoaderCircle,
  done: Check,
  not_found: CircleSlash,
  skipped: CircleSlash,
  failed: X,
}

/** A state this version does not know (a newer backend) reads as waiting. */
const known = (state: string | undefined): SyncStepState =>
  state !== undefined && state in ICONS ? (state as SyncStepState) : 'pending'

export function SyncSteps({ job }: { job: SyncJob }) {
  return (
    <ol className="space-y-2" aria-label="Sync progress">
      {STEP_ORDER.map((step) => {
        const state = known(job.steps[step])
        // A running step of a stalled job is not progressing: stopped, no spinner.
        const stopped = state === 'running' && !!job.stalled
        const Icon = stopped ? CircleSlash : ICONS[state]
        return (
          <li
            key={step}
            className="flex items-center gap-3"
            data-state={stopped ? 'stopped' : state}
          >
            <Icon
              aria-hidden="true"
              className={cn(
                'size-4',
                state === 'running' && !stopped && 'animate-spin',
                stopped && 'text-muted-foreground',
                state === 'done' && 'text-emerald-600',
                state === 'failed' && 'text-destructive',
                (state === 'pending' || state === 'not_found' || state === 'skipped') &&
                  'text-muted-foreground',
              )}
            />
            <span className="flex-1">{STEP_LABELS[step]}</span>
            <span className="text-muted-foreground text-sm">
              {stopped ? 'Stopped' : STEP_STATE_LABELS[state]}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
