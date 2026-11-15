import { useEffect, useState } from 'react'

import { Loaded } from '@/components/Loaded'

import { useDiscoveryStatus } from './api'
import { describeDiscovery } from './messages'

/** Discovery state only: no scores, percentages or ranked lists (recommendations: Phase 5). */
export function DiscoveryCard() {
  const status = useDiscoveryStatus()
  // "updated 5 minutes ago" advances while shown, without a new status.
  const now = useMinute(!!status.data?.last_completed_at)
  // A failed poll keeps the card (CR-1); only a failed first load shows the error.
  return (
    <Loaded
      query={status}
      loading={null}
      failed={
        <p role="alert" className="text-muted-foreground text-sm">
          Could not load project discovery. Please refresh the page.
        </p>
      }
    >
      {(data) => <DiscoveryState {...describeDiscovery(data, now)} />}
    </Loaded>
  )
}

/** The current time, renewed every minute while `ticking`. */
function useMinute(ticking: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!ticking) return
    const timer = setInterval(() => setNow(Date.now()), 60_000)
    return () => clearInterval(timer)
  }, [ticking])
  return now
}

function DiscoveryState({ text, alert }: { text: string; alert: boolean }) {
  return (
    <section className="space-y-1 rounded-md border p-4" aria-labelledby="discovery-heading">
      <h2 id="discovery-heading" className="font-medium">
        Project discovery
      </h2>
      {alert ? (
        <p role="alert" className="text-destructive text-sm">
          {text}
        </p>
      ) : (
        <p aria-live="polite" className="text-sm">
          {text}
        </p>
      )}
    </section>
  )
}
