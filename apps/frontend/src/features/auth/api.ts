import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type { DisconnectResult, Me } from '@/api/types'

export const meQueryKey = ['auth', 'me'] as const

export const GITHUB_SIGN_IN_URL = '/api/v1/auth/github'

export function useMe() {
  return useQuery<Me, ApiError>({
    queryKey: meQueryKey,
    queryFn: () => apiFetch<Me>('/auth/me'),
    retry: (failureCount, error) => error.status !== 401 && failureCount < 2,
    staleTime: 60_000,
  })
}

function useSignOutMutation<T>(path: string) {
  const queryClient = useQueryClient()
  return useMutation<T, ApiError>({
    mutationFn: () => apiFetch<T>(path, { method: 'POST' }),
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
