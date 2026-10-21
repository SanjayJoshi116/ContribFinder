import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type { DisconnectResult, Me } from '@/api/types'

export const meQueryKey = ['auth', 'me'] as const

export const GITHUB_SIGN_IN_URL = '/api/v1/auth/github'

/** Mutation `meta` key marking the user's own sign-out: the query client then ignores the
 * 401s of requests still in flight instead of reporting an ended session. */
export const ENDS_SESSION_META_KEY = 'endsSession'
const endsSessionMeta = { [ENDS_SESSION_META_KEY]: true }

export function useMe() {
  return useQuery<Me, ApiError>({
    queryKey: meQueryKey,
    queryFn: () => apiFetch<Me>('/auth/me'),
    staleTime: 60_000,
  })
}

function useSignOutMutation<T>(path: string) {
  const queryClient = useQueryClient()
  return useMutation<T, ApiError>({
    mutationFn: () => apiFetch<T>(path, { method: 'POST' }),
    meta: endsSessionMeta,
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: meQueryKey })
    },
  })
}

export function useLogout() {
  return useSignOutMutation<void>('/auth/logout')
}

export function useDisconnectGitHub() {
  return useSignOutMutation<DisconnectResult>('/auth/github/disconnect')
}

/** Deletes GitHub-derived data; the account and connection stay, so the dashboard falls
 * through to onboarding. */
export function useDeleteGitHubData() {
  const queryClient = useQueryClient()
  return useMutation<void, ApiError>({
    mutationFn: () => apiFetch<void>('/profile/github-data', { method: 'DELETE' }),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: ['profile'] })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: meQueryKey }),
        queryClient.invalidateQueries({ queryKey: ['sync'] }),
      ])
    },
  })
}

/** Deletes the account and everything in it; the session ends. */
export function useDeleteAccount() {
  const queryClient = useQueryClient()
  return useMutation<void, ApiError>({
    mutationFn: () => apiFetch<void>('/auth/account', { method: 'DELETE' }),
    meta: endsSessionMeta,
    onSuccess: () => queryClient.clear(),
  })
}
