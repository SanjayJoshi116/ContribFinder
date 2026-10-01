import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { ApiError, apiFetch } from '@/api/client'
import type { RecommendationDetail, RecommendationPage, RecommendationStatus } from '@/api/types'
import { isActive } from '@/features/sync/api'

// Under ['profile'], so a completed sync (useSyncStatus) invalidates them too.
const ROOT = ['profile', 'recommendations'] as const
export const recommendationStatusKey = [...ROOT, 'status'] as const
export const recommendationListKey = [...ROOT, 'list'] as const
export const recommendationDetailKey = (id: number) => [...ROOT, 'detail', id] as const
export const RECOMMENDATION_POLL_INTERVAL_MS = 3000

export const FILTER_KEYS = ['language', 'framework', 'activity', 'size', 'match'] as const
export type FilterKey = (typeof FILTER_KEYS)[number]
export type RecommendationFilters = Partial<Record<FilterKey, string>> & { page?: number }

/** `/recommendations?...` with filters in a stable order; empty values are left out. */
export function recommendationsPath(filters: RecommendationFilters): string {
  const params = new URLSearchParams()
  for (const key of FILTER_KEYS) {
    const value = filters[key]
    if (value) params.set(key, value)
  }
  if (filters.page && filters.page > 1) params.set('page', String(filters.page))
  const query = params.toString()
  return query ? `/recommendations?${query}` : '/recommendations'
}

/** Latest generation job and counts. Polls while a generation runs, and refreshes the list
 * once it finishes. A short generation can start and finish between two polls, so any newly
 * seen finished job refreshes the list, not only one that was seen running. */
export function useRecommendationStatus(enabled = true) {
  const queryClient = useQueryClient()
  const status = useQuery<RecommendationStatus, ApiError>({
    queryKey: recommendationStatusKey,
    queryFn: () => apiFetch<RecommendationStatus>('/recommendations/status'),
    enabled,
    refetchInterval: (query) =>
      isActive(query.state.data?.job) ? RECOMMENDATION_POLL_INTERVAL_MS : false,
  })
  const job = status.data?.job
  const jobKey = status.data ? `${job?.id ?? ''}:${job?.status ?? ''}` : null
  const active = isActive(job)
  const previousKey = useRef<string | null>(null)
  useEffect(() => {
    if (jobKey === null) return
    if (previousKey.current !== null && previousKey.current !== jobKey && !active) {
      void queryClient.invalidateQueries({ queryKey: recommendationListKey })
    }
    previousKey.current = jobKey
  }, [jobKey, active, queryClient])
  return status
}

export function useRecommendations(filters: RecommendationFilters, enabled = true) {
  const path = recommendationsPath(filters)
  return useQuery<RecommendationPage, ApiError>({
    queryKey: [...recommendationListKey, path],
    queryFn: () => apiFetch<RecommendationPage>(path),
    enabled,
    placeholderData: (previous) => previous,
  })
}

export function useRecommendation(id: number) {
  return useQuery<RecommendationDetail, ApiError>({
    queryKey: recommendationDetailKey(id),
    queryFn: () => apiFetch<RecommendationDetail>(`/recommendations/${id}`),
    enabled: Number.isInteger(id) && id > 0,
  })
}
