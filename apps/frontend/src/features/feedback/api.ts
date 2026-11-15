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
  Recommendation,
  RecommendationDetail,
  RecommendationPage,
  SavedPage,
} from '@/api/types'
import {
  recommendationDetailKey,
  recommendationListKey,
  recommendationsRootKey,
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

/** Stops refetches that would overwrite an optimistic change to recommendation ``id``. */
const cancelRecommendation = (queryClient: QueryClient, id: number) =>
  Promise.all([
    queryClient.cancelQueries({ queryKey: recommendationListKey }),
    queryClient.cancelQueries({ queryKey: recommendationDetailKey(id) }),
  ])

/** Where a dismissal removed its recommendation: per cached list page, its index and the item.
 * A failure puts back only this item, so other cards' changes (in flight or confirmed) stay. */
interface Removed {
  pages: [readonly unknown[], number, Recommendation][]
  detail: RecommendationDetail | undefined
}

export interface SaveVariables {
  id: number
  repositoryId: number
}

/** The one unsave request: by repository, whether or not it is still recommended. */
const unsaveRepository = (repositoryId: number) =>
  apiFetch(`/saved/${repositoryId}`, { method: 'DELETE' })

function setSaved(queryClient: QueryClient, id: number, saved: boolean) {
  queryClient.setQueriesData<RecommendationPage>({ queryKey: recommendationListKey }, (page) =>
    page?.results.some((r) => r.id === id)
      ? { ...page, results: page.results.map((r) => (r.id === id ? { ...r, saved } : r)) }
      : page,
  )
  queryClient.setQueryData<RecommendationDetail>(recommendationDetailKey(id), (detail) =>
    detail ? { ...detail, saved } : detail,
  )
}

/** Optimistic Save/Saved toggle on the list and detail caches, rolled back on error. Saving
 * needs the live recommendation; unsaving goes by repository, so it still works once a
 * background generation has dropped the recommendation (FB-3). */
function useSaveToggle(saved: boolean) {
  const queryClient = useQueryClient()
  return useMutation<unknown, ApiError, SaveVariables>({
    mutationFn: ({ id, repositoryId }) =>
      saved
        ? apiFetch(`/recommendations/${id}/save`, { method: 'POST' })
        : unsaveRepository(repositoryId),
    onMutate: async ({ id }) => {
      await cancelRecommendation(queryClient, id)
      setSaved(queryClient, id, saved)
    },
    // Only this recommendation's flag goes back: other cards keep their own changes.
    onError: (_error, { id }) => setSaved(queryClient, id, !saved),
    onSettled: () => queryClient.invalidateQueries({ queryKey: savedKey }),
  })
}

export const useSave = () => useSaveToggle(true)
export const useUnsave = () => useSaveToggle(false)

/** Pending dismissals: until they settle, an emptied list page is only optimistic. */
export const dismissMutationKey = ['feedback', 'dismiss'] as const

/** Dismissals not yet answered, per query client: counted from the start of ``onMutate`` (a
 * dismissal still cancelling queries already counts) until its request is answered. Not by
 * ``isMutating``: a mutation stays pending until its ``onSettled`` finishes, so two
 * overlapping dismissals could each see the other and neither refetch the list. */
const unanswered = new WeakMap<QueryClient, number>()

const begin = (queryClient: QueryClient) =>
  unanswered.set(queryClient, (unanswered.get(queryClient) ?? 0) + 1)
const answered = (queryClient: QueryClient) =>
  unanswered.set(queryClient, Math.max((unanswered.get(queryClient) ?? 1) - 1, 0))

/** One list (its filters) whatever its page: the cache key's path without ``page``. */
function listOf(key: readonly unknown[]): string {
  const path = String(key[key.length - 1])
  const [base, query = ''] = path.split('?')
  const params = new URLSearchParams(query)
  params.delete('page')
  return `${base}?${params.toString()}`
}

export interface DismissVariables {
  id: number
  reason?: DismissReason
  /** The page visit it was started in (``usePageVisit``); never sent. */
  visit?: string
}

/** Removes the recommendation from the cached lists at once; the server excludes its
 * repository from later generations. */
export function useDismiss() {
  const queryClient = useQueryClient()
  return useMutation<unknown, ApiError, DismissVariables, Removed>({
    mutationKey: dismissMutationKey,
    // A body only with a reason: a plain dismiss is the same request as before reasons.
    mutationFn: async ({ id, reason }) => {
      try {
        return await apiFetch(
          `/recommendations/${id}/dismiss`,
          reason ? { method: 'POST', json: { reason } } : { method: 'POST' },
        )
      } finally {
        answered(queryClient)
      }
    },
    onMutate: async ({ id }) => {
      begin(queryClient)
      try {
        await cancelRecommendation(queryClient, id)
      } catch (error) {
        answered(queryClient) // no request follows a failed onMutate
        throw error
      }
      const removed: Removed = {
        pages: [],
        detail: queryClient.getQueryData<RecommendationDetail>(recommendationDetailKey(id)),
      }
      for (const [key, page] of queryClient.getQueriesData<RecommendationPage>({
        queryKey: recommendationListKey,
      })) {
        const index = page?.results.findIndex((r) => r.id === id) ?? -1
        if (!page || index < 0) continue
        removed.pages.push([key, index, page.results[index]!])
        queryClient.setQueryData<RecommendationPage>(key, {
          ...page,
          count: page.count - 1,
          results: page.results.filter((r) => r.id !== id),
        })
      }
      return removed
    },
    onError: (_error, { id }, removed) => {
      if (!removed) return
      // Back at its old place (clamped), unless a refetch already brought it back on any page
      // of the same list (it may have moved to another page meanwhile).
      const present = new Set(
        queryClient
          .getQueriesData<RecommendationPage>({ queryKey: recommendationListKey })
          .filter(([, page]) => page?.results.some((r) => r.id === id))
          .map(([key]) => listOf(key)),
      )
      for (const [key, index, item] of removed.pages) {
        if (present.has(listOf(key))) continue
        queryClient.setQueryData<RecommendationPage>(key, (page) => {
          if (!page) return page
          const results = [...page.results]
          results.splice(Math.min(index, results.length), 0, item)
          return { ...page, count: page.count + 1, results }
        })
      }
      if (removed.detail) queryClient.setQueryData(recommendationDetailKey(id), removed.detail)
    },
    onSuccess: (_data, { id }) =>
      queryClient.removeQueries({ queryKey: recommendationDetailKey(id) }),
    // The list is refetched once no dismissal awaits its answer, so a page emptied by
    // dismissals shows the recommendations that followed it; an earlier refetch would bring
    // back cards still being dismissed.
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: dismissedKey }),
        queryClient.invalidateQueries({ queryKey: savedKey }),
        (unanswered.get(queryClient) ?? 0) === 0
          ? queryClient.invalidateQueries({ queryKey: recommendationListKey })
          : undefined,
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
        queryClient.invalidateQueries({ queryKey: recommendationsRootKey }),
        // Shows the generation the restore started.
        queryClient.invalidateQueries({ queryKey: recommendationStatusKey }),
      ]),
  })
}

/** Unsave from the saved-projects page, whether or not the project is still recommended. */
export function useUnsaveRepository() {
  const queryClient = useQueryClient()
  return useMutation<unknown, ApiError, number>({
    mutationFn: unsaveRepository,
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: savedKey }),
        queryClient.invalidateQueries({ queryKey: recommendationsRootKey }),
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
