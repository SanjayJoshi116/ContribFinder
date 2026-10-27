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
    queryFn: () =>
      fetchStatusAndRefresh(
        queryClient,
        syncStatusKey,
        () => apiFetch<SyncStatus>('/sync/status'),
        () =>
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
    onSuccess: (job) => {
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

/** All synced repositories (the per-sync cap keeps this to one page of up to 100). */
export function useRepositories(enabled = true) {
  return useQuery<RepositoryPage, ApiError>({
    queryKey: repositoriesKey,
    queryFn: () => apiFetch<RepositoryPage>('/profile/repositories?page_size=100'),
    enabled,
  })
}
