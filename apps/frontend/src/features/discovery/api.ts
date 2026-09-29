import { useQuery } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type { DiscoveryStatus } from '@/api/types'
import { isActive } from '@/features/sync/api'

// Under ['profile'], so a completed sync (useSyncStatus) invalidates it: a completed sync
// starts a new discovery run.
export const discoveryStatusKey = ['profile', 'discovery'] as const
export const DISCOVERY_POLL_INTERVAL_MS = 3000

/** Latest repository discovery job and pool counts. Polls while a run is in progress. */
export function useDiscoveryStatus(enabled = true) {
  return useQuery<DiscoveryStatus, ApiError>({
    queryKey: discoveryStatusKey,
    queryFn: () => apiFetch<DiscoveryStatus>('/discovery/status'),
    enabled,
    refetchInterval: (query) =>
      isActive(query.state.data?.job) ? DISCOVERY_POLL_INTERVAL_MS : false,
  })
}
