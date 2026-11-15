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
 * running, from the status queries the dashboard already polls. Null when idle. With
 * `fetchStages` false the discovery and recommendation observers are passive: the discovery
 * card and the recommendation list fetch and poll them, and a second active observer would
 * refetch on mount. Pass true only while those will not be shown (profile loaded but not
 * analyzed), so the stages are still followed; false while the profile loads, since the cards
 * mount right after. */
export function usePipelineStage(fetchStages: boolean): PipelineStage | null {
  const sync = useSyncStatus()
  const discovery = useDiscoveryStatus(fetchStages)
  const recommendations = useRecommendationStatus(fetchStages)

  const syncJob = sync.data?.job
  const discoveryJob = discovery.data?.job
  // The first active job of the chain decides; a stalled one says so instead of its stage.
  const current = [syncJob, discoveryJob, recommendations.data?.job].find((job) => isActive(job))
  if (!current) return null
  if (current.stalled) return 'stalled'
  if (current === syncJob) return current.steps.analysis === 'running' ? 'analyzing' : 'syncing'
  return current === discoveryJob ? 'finding' : 'preparing'
}
