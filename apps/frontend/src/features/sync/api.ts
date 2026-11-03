import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type { GitHubProfile, RepositoryPage, SyncJob, SyncStatus } from '@/api/types'
import { refreshDataVersions } from '@/app/dataVersions'
import { fetchStatusAndRefresh, isActive } from '@/app/jobTransitions'

// Not under ['jobs']: a finished sync invalidates that prefix and must not invalidate itself.
export const syncStatusKey = ['sync', 'status'] as const
export const githubProfileKey = ['profile', 'github'] as const
export const repositoriesKey = ['profile', 'repositories'] as const

export const POLL_INTERVAL_MS = 2000

/** Latest sync job and last successful sync. Polls while a job is in progress; a newly
 * finished sync asks for the data versions (which refetch the areas it changed) and the
 * discovery and generation statuses (['jobs']), since it starts a new discovery run. */
export function useSyncStatus() {
  const queryClient = useQueryClient()
  return useQuery<SyncStatus, ApiError>({
    queryKey: syncStatusKey,
    queryFn: ({ signal }) =>
      fetchStatusAndRefresh<SyncStatus>(queryClient, syncStatusKey, '/sync/status', signal, () =>
        Promise.all([
          refreshDataVersions(queryClient),
          queryClient.invalidateQueries({ queryKey: ['jobs'] }),
        ]),
      ),
    staleTime: 0,
    refetchInterval: (query) => (isActive(query.state.data?.job) ? POLL_INTERVAL_MS : false),
  })
}

export function useStartSync() {
  const queryClient = useQueryClient()
  return useMutation<SyncJob, ApiError>({
    mutationFn: () => apiFetch<SyncJob>('/profile/sync', { method: 'POST' }),
    onSuccess: async (job) => {
      // A status fetch from before the start would answer with the previous job and stop the
      // polling (APP-4); cancelled, it restores the cached status, which the job replaces.
      await queryClient.cancelQueries({ queryKey: syncStatusKey })
      queryClient.setQueryData<SyncStatus>(syncStatusKey, (previous) => ({
        job,
        last_synced_at: previous?.last_synced_at ?? null,
      }))
    },
  })
}

export function useGitHubProfile(enabled = true) {
  return useQuery<GitHubProfile, ApiError>({
    queryKey: githubProfileKey,
    queryFn: () => apiFetch<GitHubProfile>('/profile/github'),
    enabled,
  })
}

const REPOSITORY_PAGE_SIZE = 100

/** All synced repositories as one page: follows `next` until it is null, so every
 * repository shows whatever the per-sync cap (the default cap fits in one request). The
 * result keeps the first page's `count`. */
export function useRepositories(enabled = true) {
  return useQuery<RepositoryPage, ApiError>({
    queryKey: repositoriesKey,
    queryFn: async ({ signal }) => {
      const path = '/profile/repositories'
      const first = await apiFetch<RepositoryPage>(`${path}?page_size=${REPOSITORY_PAGE_SIZE}`, {
        signal,
      })
      const results = [...first.results]
      let next = first.next
      while (next) {
        // The link's own query, whatever it carries (page, page size).
        const more = await apiFetch<RepositoryPage>(
          path + new URL(next, window.location.origin).search,
          { signal },
        )
        results.push(...more.results)
        next = more.next
      }
      return { ...first, next: null, results }
    },
    enabled,
  })
}
