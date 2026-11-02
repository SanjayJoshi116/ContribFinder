import { useIsMutating, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'

import { ApiError, apiFetch } from '@/api/client'
import type { DisconnectResult, Me } from '@/api/types'
import { dataVersionsKey } from '@/app/dataVersions'
import { ENDS_SESSION_META_KEY, leaveSignedIn, meQueryKey } from '@/app/session'

export { ENDS_SESSION_META_KEY, meQueryKey }

export const GITHUB_SIGN_IN_URL = '/api/v1/auth/github'

const endsSessionMeta = { [ENDS_SESSION_META_KEY]: true }

/** Prefix of every account action (log out, disconnect, delete data, delete account): one runs
 * at a time (`useAccountActionPending`). */
export const accountMutationKey = ['account'] as const

export function useMe() {
  return useQuery<Me, ApiError>({
    queryKey: meQueryKey,
    queryFn: () => apiFetch<Me>('/auth/me'),
    staleTime: 60_000,
  })
}

/** The navigation of the account actions lives in the hooks: per-call callbacks are skipped
 * once the page that started the action unmounts. */
function useReplace() {
  const navigate = useNavigate()
  return async (path: string) => {
    await navigate(path, { replace: true })
  }
}

interface SignOut {
  /** Its part of the mutation key, under `accountMutationKey`. */
  name: string
  path: string
  method?: 'POST' | 'DELETE'
}

function useSignOutMutation<T>({ name, path, method = 'POST' }: SignOut) {
  const queryClient = useQueryClient()
  const replace = useReplace()
  return useMutation<T, ApiError>({
    mutationKey: [...accountMutationKey, name],
    mutationFn: () => apiFetch<T>(path, { method }),
    meta: endsSessionMeta,
    onSuccess: () => leaveSignedIn(queryClient, replace, '/'),
  })
}

export function useLogout() {
  return useSignOutMutation<void>({ name: 'logout', path: '/auth/logout' })
}

export function useDisconnectGitHub() {
  return useSignOutMutation<DisconnectResult>({
    name: 'disconnect',
    path: '/auth/github/disconnect',
  })
}

/** Deletes GitHub-derived data; the account and connection stay, so the dashboard falls
 * through to onboarding. */
export function useDeleteGitHubData() {
  const queryClient = useQueryClient()
  const replace = useReplace()
  return useMutation<void, ApiError>({
    mutationKey: [...accountMutationKey, 'delete-data'],
    mutationFn: () => apiFetch<void>('/profile/github-data', { method: 'DELETE' }),
    onSuccess: async () => {
      const deleted = [{ queryKey: ['profile'] }, { queryKey: ['jobs'] }]
      await Promise.all(deleted.map((filters) => queryClient.cancelQueries(filters)))
      // The sync status now has no last sync: the dashboard redirects to onboarding.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: meQueryKey }),
        queryClient.invalidateQueries({ queryKey: ['sync'] }),
      ])
      await replace('/onboarding')
      // No page observes them any more.
      for (const filters of deleted) queryClient.removeQueries(filters)
      // Reset, not removed: the signed-in layout still observes it. Its data goes undefined,
      // so useDataVersions forgets the last value and the refetch refetches nothing (U-7).
      void queryClient.resetQueries({ queryKey: dataVersionsKey })
    },
  })
}

/** Deletes the account and everything in it; the session ends. */
export function useDeleteAccount() {
  return useSignOutMutation<void>({
    name: 'delete-account',
    path: '/auth/account',
    method: 'DELETE',
  })
}

/** Whether an account action is in progress: every other one waits. */
export function useAccountActionPending(): boolean {
  return useIsMutating({ mutationKey: accountMutationKey }) > 0
}
