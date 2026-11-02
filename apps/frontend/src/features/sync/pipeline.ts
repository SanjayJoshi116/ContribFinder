import { isActive } from '@/app/jobTransitions'
import { useDiscoveryStatus } from '@/features/discovery/api'
import { useRecommendationStatus } from '@/features/recommendations/api'

import { useSyncStatus } from './api'
import { STALLED_NOTICE } from './messages'

export type PipelineStage = 'syncing' | 'analyzing' | 'finding' | 'preparing' | 'stalled'

export const STAGE_TEXT: Record<PipelineStage, string> = {
  syncing: 'Syncing GitHub data…',
  analyzing: 'Analyzing your profile…',
  finding: 'Finding projects…',
  preparing: 'Preparing recommendations…',
  stalled: `${STALLED_NOTICE}, or press Refresh.`,
}

/** Which stage of the refresh pipeline (sync → analysis → discovery → recommendations) is
 * running, from the status queries the dashboard already polls. Null when idle. The discovery
 * and recommendation observers are passive (disabled): the discovery card and the
 * recommendation list fetch and poll them, and a second active observer would refetch on
 * mount. */
export function usePipelineStage(): PipelineStage | null {
  const sync = useSyncStatus()
  const discovery = useDiscoveryStatus(false)
  const recommendations = useRecommendationStatus(false)

  const syncJob = sync.data?.job
  const discoveryJob = discovery.data?.job
  // The first active job of the chain decides; a stalled one says so instead of its stage.
  const current = [syncJob, discoveryJob, recommendations.data?.job].find((job) => isActive(job))
  if (!current) return null
  if (current.stalled) return 'stalled'
  if (current === syncJob) return current.steps.analysis === 'running' ? 'analyzing' : 'syncing'
  return current === discoveryJob ? 'finding' : 'preparing'
}
