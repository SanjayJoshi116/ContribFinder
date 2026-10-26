import { useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type { RecommendationDetail, RecommendationPage, RecommendationStatus } from '@/api/types'
import { fetchStatusAndRefresh, isActive } from '@/app/jobTransitions'

// Under ['profile'], so a completed sync (useSyncStatus) invalidates them too.
const ROOT = ['profile', 'recommendations'] as const
// Job status keys live under ['jobs'], never ['profile']: a status fetch invalidates the
// ['profile'] prefix when its job finishes, and must not invalidate itself.
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

/** Latest generation job and counts. Polls while a generation runs, and refreshes the list
 * once per newly seen finished job, also one that started and finished between two polls.
 * Every profile analysis ends in a generation, also one no sync started (`reanalyze_profiles`),
 * so all of ['profile'] is refreshed: the list, details, issues, saved entries (they show the
 * current recommendation) and the developer profile. The status key is under ['jobs']. */
export function useRecommendationStatus(enabled = true) {
  const queryClient = useQueryClient()
  return useQuery<RecommendationStatus, ApiError>({
    queryKey: recommendationStatusKey,
    queryFn: () =>
      fetchStatusAndRefresh(
        queryClient,
        recommendationStatusKey,
        () => apiFetch<RecommendationStatus>('/recommendations/status'),
        () => queryClient.invalidateQueries({ queryKey: ['profile'] }),
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
    enabled: Number.isInteger(id) && id > 0,
  })
}
