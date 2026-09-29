import { useDiscoveryStatus } from './api'
import { describeDiscovery } from './messages'

/** Discovery state only: no scores, percentages or ranked lists (recommendations: Phase 5). */
export function DiscoveryCard() {
  const status = useDiscoveryStatus()
  if (status.isPending) return null
  if (status.isError) {
    return (
      <p role="alert" className="text-muted-foreground text-sm">
        Could not load project discovery. Please refresh the page.
      </p>
    )
  }
  const { text, alert } = describeDiscovery(status.data)
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
