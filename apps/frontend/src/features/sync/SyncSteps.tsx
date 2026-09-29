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

export function SyncSteps({ job }: { job: SyncJob }) {
  return (
    <ol className="space-y-2" aria-label="Sync progress">
      {STEP_ORDER.map((step) => {
        const state: SyncStepState = job.steps[step] ?? 'pending'
        const Icon = ICONS[state]
        return (
          <li key={step} className="flex items-center gap-3" data-state={state}>
            <Icon
              aria-hidden="true"
              className={cn(
                'size-4',
                state === 'running' && 'animate-spin',
                state === 'done' && 'text-emerald-600',
                state === 'failed' && 'text-destructive',
                (state === 'pending' || state === 'not_found' || state === 'skipped') &&
                  'text-muted-foreground',
              )}
            />
            <span className="flex-1">{STEP_LABELS[step]}</span>
            <span className="text-muted-foreground text-sm">{STEP_STATE_LABELS[state]}</span>
          </li>
        )
      })}
    </ol>
  )
}
