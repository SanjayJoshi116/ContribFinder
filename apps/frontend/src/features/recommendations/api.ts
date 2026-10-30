import { useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type { RecommendationDetail, RecommendationPage, RecommendationStatus } from '@/api/types'
import { refreshDataVersions } from '@/app/dataVersions'
import { fetchStatusAndRefresh, isActive } from '@/app/jobTransitions'

// Under ['profile'], so delete-data removes them; the `recommendations` data version
// refetches them (src/app/dataVersions.ts).
const ROOT = ['profile', 'recommendations'] as const
// Job status keys live under ['jobs'], never ['profile']: the data versions invalidate
// ['profile'] queries, and a status must not be refetched by them.
export const recommendationStatusKey = ['jobs', 'recommendations'] as const
export const recommendationListKey = [...ROOT, 'list'] as const
export const recommendationDetailKey = (id: number) => [...ROOT, 'detail', id] as const
export const RECOMMENDATION_POLL_INTERVAL_MS = 3000

export const FILTER_KEYS = [
  'language',
  'framework',
  'activity',
  'size',
  'match',
  'difficulty',
  'contribution_type',
] as const
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

/** Latest generation job and counts. Polls while a generation runs, and asks for the data
 * versions once per newly seen finished job, also one that started and finished between two
 * polls: they refetch the recommendations, and the developer profile only when it was
 * re-analyzed. The status key is under ['jobs']. */
export function useRecommendationStatus(enabled = true) {
  const queryClient = useQueryClient()
  return useQuery<RecommendationStatus, ApiError>({
    queryKey: recommendationStatusKey,
    queryFn: () =>
      fetchStatusAndRefresh(
        queryClient,
        recommendationStatusKey,
        () => apiFetch<RecommendationStatus>('/recommendations/status'),
        () => refreshDataVersions(queryClient),
      ),
    staleTime: 0,
    enabled,
    refetchInterval: (query) =>
      isActive(query.state.data?.job) ? RECOMMENDATION_POLL_INTERVAL_MS : false,
  })
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
  })
}
