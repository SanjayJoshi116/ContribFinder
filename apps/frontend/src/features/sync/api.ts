import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type { GitHubProfile, RepositoryPage, SyncJob, SyncStatus } from '@/api/types'

export const syncStatusKey = ['sync', 'status'] as const
export const githubProfileKey = ['profile', 'github'] as const
export const repositoriesKey = ['profile', 'repositories'] as const

const ACTIVE: ReadonlySet<SyncJob['status']> = new Set(['PENDING', 'RUNNING', 'RETRYING'])
export const POLL_INTERVAL_MS = 2000

export function isActive(job: SyncJob | null | undefined): boolean {
  return !!job && ACTIVE.has(job.status)
}

/** Latest sync job and last successful sync. Polls while a job is in progress. */
export function useSyncStatus() {
  const queryClient = useQueryClient()
  return useQuery<SyncStatus, ApiError>({
    queryKey: syncStatusKey,
    queryFn: async () => {
      const status = await apiFetch<SyncStatus>('/sync/status')
      if (status.job?.status === 'COMPLETED') {
        // Fresh data landed: refetch anything derived from it.
        await queryClient.invalidateQueries({ queryKey: ['profile'] })
      }
      return status
    },
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
