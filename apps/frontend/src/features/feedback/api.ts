import {
  type InfiniteData,
  type QueryClient,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type {
  DismissedPage,
  DismissReason,
  FeedbackAction,
  RecommendationDetail,
  RecommendationPage,
  SavedPage,
} from '@/api/types'
import {
  recommendationDetailKey,
  recommendationListKey,
  recommendationStatusKey,
} from '@/features/recommendations/api'

// Under ['profile'], so delete-data removes them; the `recommendations` data version
// refetches the saved list (src/app/dataVersions.ts).
export const savedKey = ['profile', 'saved'] as const
export const dismissedKey = ['profile', 'dismissed'] as const

/** Fire-and-forget interaction event: never blocks navigation, never shows an error.
 * ``opened_issue`` needs the issue id, one of the recommendation's relevant issues. */
export function recordFeedback(
  recommendationId: number,
  action: FeedbackAction,
  extra: { issue_id?: number } = {},
): void {
  apiFetch<void>(`/recommendations/${recommendationId}/feedback`, {
    method: 'POST',
    json: { action, ...extra },
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

/** Pending dismissals: until they settle, an emptied list page is only optimistic. */
export const dismissMutationKey = ['feedback', 'dismiss'] as const

export interface DismissVariables {
  id: number
  reason?: DismissReason
}

/** Removes the recommendation from the cached lists at once; the server excludes its
 * repository from later generations. */
export function useDismiss() {
  const queryClient = useQueryClient()
  return useMutation<unknown, ApiError, DismissVariables, Snapshot>({
    mutationKey: dismissMutationKey,
    // A body only with a reason: a plain dismiss is the same request as before reasons.
    mutationFn: ({ id, reason }) =>
      apiFetch(
        `/recommendations/${id}/dismiss`,
        reason ? { method: 'POST', json: { reason } } : { method: 'POST' },
      ),
    onMutate: async ({ id }) => {
      const previous = await snapshot(queryClient, id)
      queryClient.setQueriesData<RecommendationPage>({ queryKey: recommendationListKey }, (page) =>
        page && page.results.some((r) => r.id === id)
          ? { ...page, count: page.count - 1, results: page.results.filter((r) => r.id !== id) }
          : page,
      )
      return previous
    },
    onError: (_error, { id }, previous) => rollback(queryClient, id, previous),
    onSuccess: (_data, { id }) =>
      queryClient.removeQueries({ queryKey: recommendationDetailKey(id) }),
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
        // Shows the generation the restore started.
        queryClient.invalidateQueries({ queryKey: recommendationStatusKey }),
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

/** Entries per request; "Show more" loads the next page. */
export const LIST_PAGE_SIZE = 50

/** `/saved` or `/dismissed`, one page at a time, so every entry can be reached. Each page
 * continues after the previous page's last entry (the `cursor` in `next`), so saves and
 * removals between "Show more" clicks never repeat or skip an entry. An invalidation refetches
 * all loaded pages in order, so entries already shown stay listed. */
function usePagedList<P extends { next?: string | null }>(key: readonly unknown[], path: string) {
  return useInfiniteQuery<P, ApiError, InfiniteData<P>, readonly unknown[], string | null>({
    queryKey: key,
    queryFn: ({ pageParam }) =>
      apiFetch<P>(
        pageParam
          ? `${path}?page_size=${LIST_PAGE_SIZE}&cursor=${encodeURIComponent(pageParam)}`
          : `${path}?page_size=${LIST_PAGE_SIZE}`,
      ),
    initialPageParam: null,
    getNextPageParam: (last) =>
      (last.next && new URL(last.next, window.location.origin).searchParams.get('cursor')) ||
      undefined,
  })
}

export const useSaved = () => usePagedList<SavedPage>(savedKey, '/saved')
export const useDismissed = () => usePagedList<DismissedPage>(dismissedKey, '/dismissed')
