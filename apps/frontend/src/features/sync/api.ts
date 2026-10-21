import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type { GitHubProfile, RepositoryPage, SyncJob, SyncStatus } from '@/api/types'
import { fetchStatusAndRefresh, isActive } from '@/app/jobTransitions'

export const syncStatusKey = ['sync', 'status'] as const
export const githubProfileKey = ['profile', 'github'] as const
export const repositoriesKey = ['profile', 'repositories'] as const

export const POLL_INTERVAL_MS = 2000

/** Latest sync job and last successful sync. Polls while a job is in progress; a newly
 * finished sync refetches everything derived from GitHub data (all of ['profile']). */
export function useSyncStatus() {
  const queryClient = useQueryClient()
  return useQuery<SyncStatus, ApiError>({
    queryKey: syncStatusKey,
    queryFn: () =>
      fetchStatusAndRefresh(
        queryClient,
        syncStatusKey,
        () => apiFetch<SyncStatus>('/sync/status'),
        () => queryClient.invalidateQueries({ queryKey: ['profile'] }),
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
