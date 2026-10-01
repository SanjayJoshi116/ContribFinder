import { type QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type {
  DismissedPage,
  FeedbackAction,
  RecommendationDetail,
  RecommendationPage,
  SavedPage,
} from '@/api/types'
import { recommendationDetailKey, recommendationListKey } from '@/features/recommendations/api'

// Under ['profile'], so a completed sync refreshes them with everything else.
export const savedKey = ['profile', 'saved'] as const
export const dismissedKey = ['profile', 'dismissed'] as const

/** Fire-and-forget interaction event: never blocks navigation, never shows an error. */
export function recordFeedback(recommendationId: number, action: FeedbackAction): void {
  apiFetch<void>(`/recommendations/${recommendationId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
    keepalive: true,
  }).catch(() => undefined)
}

type ListSnapshot = [readonly unknown[], RecommendationPage | undefined][]

interface Snapshot {
  lists: ListSnapshot
  detail: RecommendationDetail | undefined
}

async function snapshot(queryClient: QueryClient, id: number): Promise<Snapshot> {
  await queryClient.cancelQueries({ queryKey: recommendationListKey })
  await queryClient.cancelQueries({ queryKey: recommendationDetailKey(id) })
  return {
    lists: queryClient.getQueriesData<RecommendationPage>({ queryKey: recommendationListKey }),
    detail: queryClient.getQueryData<RecommendationDetail>(recommendationDetailKey(id)),
  }
}

function rollback(queryClient: QueryClient, id: number, previous: Snapshot | undefined) {
  if (!previous) return
  for (const [key, data] of previous.lists) queryClient.setQueryData(key, data)
  queryClient.setQueryData(recommendationDetailKey(id), previous.detail)
}

/** Optimistic Save/Saved toggle on the list and detail caches, rolled back on error. */
function useSaveToggle(saved: boolean) {
  const queryClient = useQueryClient()
  return useMutation<unknown, ApiError, number, Snapshot>({
    mutationFn: (id) =>
      apiFetch(`/recommendations/${id}/save`, { method: saved ? 'POST' : 'DELETE' }),
    onMutate: async (id) => {
      const previous = await snapshot(queryClient, id)
      queryClient.setQueriesData<RecommendationPage>({ queryKey: recommendationListKey }, (page) =>
        page
          ? { ...page, results: page.results.map((r) => (r.id === id ? { ...r, saved } : r)) }
          : page,
      )
      queryClient.setQueryData<RecommendationDetail>(recommendationDetailKey(id), (detail) =>
        detail ? { ...detail, saved } : detail,
      )
      return previous
    },
    onError: (_error, id, previous) => rollback(queryClient, id, previous),
    onSettled: () => queryClient.invalidateQueries({ queryKey: savedKey }),
  })
}

export const useSave = () => useSaveToggle(true)
export const useUnsave = () => useSaveToggle(false)

/** Removes the recommendation from the cached lists at once; the server excludes its
 * repository from later generations. */
export function useDismiss() {
  const queryClient = useQueryClient()
  return useMutation<unknown, ApiError, number, Snapshot>({
    mutationFn: (id) => apiFetch(`/recommendations/${id}/dismiss`, { method: 'POST' }),
    onMutate: async (id) => {
      const previous = await snapshot(queryClient, id)
      queryClient.setQueriesData<RecommendationPage>({ queryKey: recommendationListKey }, (page) =>
        page && page.results.some((r) => r.id === id)
          ? { ...page, count: page.count - 1, results: page.results.filter((r) => r.id !== id) }
          : page,
      )
      return previous
    },
    onError: (_error, id, previous) => rollback(queryClient, id, previous),
    onSuccess: (_data, id) => queryClient.removeQueries({ queryKey: recommendationDetailKey(id) }),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: dismissedKey }),
        queryClient.invalidateQueries({ queryKey: savedKey }),
      ]),
  })
}

/** Undo a dismissal. The server starts a generation, which brings the project back. */
export function useRestore() {
  const queryClient = useQueryClient()
  return useMutation<unknown, ApiError, number>({
    mutationFn: (repositoryId) => apiFetch(`/dismissed/${repositoryId}`, { method: 'DELETE' }),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: dismissedKey }),
        queryClient.invalidateQueries({ queryKey: ['profile', 'recommendations'] }),
      ]),
  })
}

/** Unsave from the saved-projects page, whether or not the project is still recommended. */
export function useUnsaveRepository() {
  const queryClient = useQueryClient()
  return useMutation<unknown, ApiError, number>({
    mutationFn: (repositoryId) => apiFetch(`/saved/${repositoryId}`, { method: 'DELETE' }),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: savedKey }),
        queryClient.invalidateQueries({ queryKey: ['profile', 'recommendations'] }),
      ]),
  })
}

export function useSaved() {
  return useQuery<SavedPage, ApiError>({
    queryKey: savedKey,
    queryFn: () => apiFetch<SavedPage>('/saved?page_size=100'),
  })
}

export function useDismissed() {
  return useQuery<DismissedPage, ApiError>({
    queryKey: dismissedKey,
    queryFn: () => apiFetch<DismissedPage>('/dismissed?page_size=100'),
  })
}
