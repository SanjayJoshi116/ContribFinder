import { type QueryClient, hashKey } from '@tanstack/react-query'

import { SESSION_ENDED_PATH } from '@/features/auth/authErrors'

/** Session primitives shared by the query client (`queryClient.ts`) and the auth hooks
 * (`features/auth/api.ts`); neither imports the other. */

export const meQueryKey = ['auth', 'me'] as const

/** Mutation `meta` key marking the user's own sign-out: the query client then ignores the
 * 401s of requests still in flight instead of reporting an ended session. */
export const ENDS_SESSION_META_KEY = 'endsSession'

/** Replaces the current location, e.g. `(path) => router.navigate(path, { replace: true })`. */
export type Navigate = (path: string) => Promise<void>

const meQueryHash = hashKey(meQueryKey)
export const isMe = (query: { queryHash: string }) => query.queryHash === meQueryHash

/** Leaves the signed-in pages for `path`: nothing is refetched on the way, and the identity
 * goes first so the sign-in page asks the server again instead of bouncing back to /app. */
async function leave(queryClient: QueryClient, navigate: Navigate, path: string): Promise<void> {
  await queryClient.cancelQueries()
  queryClient.removeQueries({ queryKey: meQueryKey, exact: true })
  await navigate(path)
}

/** A 401 while signed in: the sign-in page with the session-ended notice, which drops the
 * rest (`clearSignedInData`) once no signed-in page is left to refetch it. */
export function endSession(queryClient: QueryClient, navigate: Navigate): Promise<void> {
  return leave(queryClient, navigate, SESSION_ENDED_PATH)
}

/** Leaving on purpose (log out, disconnect, account deletion): no notice, and the rest goes
 * once no signed-in page observes it. */
export async function leaveSignedIn(
  queryClient: QueryClient,
  navigate: Navigate,
  path: string,
): Promise<void> {
  await leave(queryClient, navigate, path)
  clearSignedInData(queryClient)
}

/** Drops every cached query except the identity, and pending mutation state. */
export function clearSignedInData(queryClient: QueryClient): void {
  queryClient.removeQueries({ predicate: (query) => !isMe(query) })
  queryClient.getMutationCache().clear()
}
