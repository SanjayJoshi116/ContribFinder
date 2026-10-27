import { useQuery, useQueryClient, type QueryClient, type QueryKey } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { ApiError, apiFetch } from '@/api/client'
import type { DataVersions } from '@/api/types'

/** Outside ['profile'] and ['jobs']: a versions fetch invalidates ['profile'] queries, and the
 * job refreshes invalidate ['jobs']; neither may invalidate the query that triggered it. */
export const dataVersionsKey = ['versions'] as const

export type DataArea = keyof DataVersions

/** The queries each area's time covers. The hidden list shows stored repository data, so a
 * background refresh reaches it through `recommendations` (U-2). */
export const AREA_KEYS: Record<DataArea, readonly QueryKey[]> = {
  github: [
    ['profile', 'github'],
    ['profile', 'repositories'],
  ],
  profile: [
    ['profile', 'developer'],
    ['profile', 'skills'],
    ['profile', 'interests'],
  ],
  recommendations: [
    ['profile', 'recommendations'],
    ['profile', 'issues'],
    ['profile', 'saved'],
    ['profile', 'dismissed'],
  ],
}

const AREAS = Object.keys(AREA_KEYS) as DataArea[]

/** Areas whose time differs (not only newer: a dismiss can make the newest time older). */
export function changedAreas(previous: DataVersions, current: DataVersions): DataArea[] {
  return AREAS.filter((area) => previous[area] !== current[area])
}

/** When each derived data area last changed. Fetched on mount, focus, route change
 * (`SignedInLayout`) and after a finished job (the status queries' refresh). The `queryFn` only
 * fetches; the comparison runs when the cached value changes, against the last value this hook
 * saw, so a cancelled or joined fetch can never refetch an area twice (U-6). Structural sharing
 * keeps the same object for an unchanged answer, so nothing runs then. Without a previous value
 * (first fetch, or after the user's data was deleted and the query reset) nothing is refetched:
 * the derived data loads on its own. Call it from one component only (`SignedInLayout`). */
export function useDataVersions(enabled = true) {
  const queryClient = useQueryClient()
  const query = useQuery<DataVersions, ApiError>({
    queryKey: dataVersionsKey,
    queryFn: () => apiFetch<DataVersions>('/sync/versions'),
    staleTime: 0,
    enabled,
  })
  const seen = useRef<DataVersions | undefined>(undefined)
  const { data } = query
  useEffect(() => {
    const previous = seen.current
    seen.current = data
    if (previous === undefined || data === undefined) return
    const keys = changedAreas(previous, data).flatMap((area) => AREA_KEYS[area])
    void Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })))
  }, [data, queryClient])
  return query
}

/** Asks for the data versions again; for refresh callbacks after a finished job. */
export function refreshDataVersions(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: dataVersionsKey })
}
