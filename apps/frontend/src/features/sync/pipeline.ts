import { isActive } from '@/app/jobTransitions'
import { useDiscoveryStatus } from '@/features/discovery/api'
import { useRecommendationStatus } from '@/features/recommendations/api'

import { useSyncStatus } from './api'

export type PipelineStage = 'syncing' | 'analyzing' | 'finding' | 'preparing'

export const STAGE_TEXT: Record<PipelineStage, string> = {
  syncing: 'Syncing GitHub data…',
  analyzing: 'Analyzing your profile…',
  finding: 'Finding projects…',
  preparing: 'Preparing recommendations…',
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
  if (isActive(syncJob)) return syncJob?.steps.analysis === 'running' ? 'analyzing' : 'syncing'
  if (isActive(discovery.data?.job)) return 'finding'
  if (isActive(recommendations.data?.job)) return 'preparing'
  return null
}
