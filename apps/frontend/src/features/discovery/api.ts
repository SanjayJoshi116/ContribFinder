import { useQuery, useQueryClient } from '@tanstack/react-query'

import type { ApiError } from '@/api/client'
import type { DiscoveryStatus } from '@/api/types'
import { fetchStatusAndRefresh, isActive } from '@/app/jobTransitions'
import { recommendationStatusKey } from '@/features/recommendations/api'

// Under ['jobs'], so a completed sync (useSyncStatus) invalidates it: a completed sync
// starts a new discovery run.
export const discoveryStatusKey = ['jobs', 'discovery'] as const
export const DISCOVERY_POLL_INTERVAL_MS = 3000

/** Latest repository discovery job and pool counts. Polls while a run is in progress. A
 * finished discovery starts a generation, so it looks for that generation right away. It
 * changes no data area, so the data versions wait for the generation (U-5). */
export function useDiscoveryStatus(enabled = true) {
  const queryClient = useQueryClient()
  return useQuery<DiscoveryStatus, ApiError>({
    queryKey: discoveryStatusKey,
    queryFn: ({ signal }) =>
      fetchStatusAndRefresh<DiscoveryStatus>(
        queryClient,
        discoveryStatusKey,
        '/discovery/status',
        signal,
        () => queryClient.invalidateQueries({ queryKey: recommendationStatusKey }),
      ),
    staleTime: 0,
    enabled,
    refetchInterval: (query) =>
      isActive(query.state.data?.job) ? DISCOVERY_POLL_INTERVAL_MS : false,
  })
}
