import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { useDiscoveryStatus } from '@/features/discovery/api'
import { recommendationStatusKey, useRecommendationStatus } from '@/features/recommendations/api'

import { isActive, useSyncStatus } from './api'

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
  const queryClient = useQueryClient()
  const sync = useSyncStatus()
  const discovery = useDiscoveryStatus(false)
  const recommendations = useRecommendationStatus(false)

  // A finished discovery starts a generation: look for it right away.
  const discovering = isActive(discovery.data?.job)
  const wasDiscovering = useRef(false)
  useEffect(() => {
    if (wasDiscovering.current && !discovering) {
      void queryClient.invalidateQueries({ queryKey: recommendationStatusKey })
    }
    wasDiscovering.current = discovering
  }, [discovering, queryClient])

  const syncJob = sync.data?.job
  if (isActive(syncJob)) return syncJob?.steps.analysis === 'running' ? 'analyzing' : 'syncing'
  if (discovering) return 'finding'
  if (isActive(recommendations.data?.job)) return 'preparing'
  return null
}
