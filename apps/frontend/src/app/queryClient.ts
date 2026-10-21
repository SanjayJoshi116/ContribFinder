import { MutationCache, QueryCache, QueryClient, hashKey } from '@tanstack/react-query'

import { ApiError } from '@/api/client'
import { ENDS_SESSION_META_KEY, meQueryKey } from '@/features/auth/api'
import { SESSION_ENDED_PATH } from '@/features/auth/authErrors'

const MAX_RETRIES = 2

/** Data derived from jobs changes only when a job finishes (the status queries refresh it)
 * or through the user's own actions (their mutations refresh it), so it is not refetched on
 * every mount or focus. Status queries set `staleTime: 0`. */
const DERIVED_STALE_TIME_MS = 5 * 60_000

/** Only failures a retry can fix: no response (network, CSRF fetch) or a server error. A 4xx
 * is the answer, and retrying it only delays showing it. */
function isRetryable(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true
  return error.status === 0 || error.status >= 500
}

const meQueryHash = hashKey(meQueryKey)
const isMe = (query: { queryHash: string }) => query.queryHash === meQueryHash

/** Leaves the signed-in app for the sign-in page with the session-ended notice. Only the
 * identity is dropped here, so the sign-in page asks the server again instead of bouncing back
 * to /app; the sign-in page drops the rest (`clearSignedInData`) once no signed-in page is left
 * to refetch it. */
async function endSession(queryClient: QueryClient, navigate: Navigate): Promise<void> {
  await queryClient.cancelQueries()
  queryClient.removeQueries({ queryKey: meQueryKey, exact: true })
  await navigate(SESSION_ENDED_PATH)
}

/** Drops every cached query except the identity, and pending mutation state. */
export function clearSignedInData(queryClient: QueryClient): void {
  queryClient.removeQueries({ predicate: (query) => !isMe(query) })
  queryClient.getMutationCache().clear()
}

function endsSession(meta: Record<string, unknown> | undefined): boolean {
  return meta?.[ENDS_SESSION_META_KEY] === true
}

/** Replaces the current location, e.g. `(path) => router.navigate(path, { replace: true })`. */
type Navigate = (path: string) => Promise<void>

interface Options {
  /** Used once when a signed-in request answers 401 (to the sign-in page), and again only after
   * `/auth/me` succeeds. */
  navigate: Navigate
  /** Tests pass 0; production keeps TanStack's exponential default. */
  retryDelay?: number
}

/** The one QueryClient setup, shared by the app and the tests. */
export function createQueryClient({ navigate, retryDelay }: Options): QueryClient {
  // The dashboard's parallel queries fail together when the session ends: react to the first.
  let signedOut = false
  const unauthenticated = (error: unknown) => {
    if (signedOut || !(error instanceof ApiError) || error.status !== 401) return
    signedOut = true
    void endSession(queryClient, navigate)
  }

  const queryClient = new QueryClient({
    queryCache: new QueryCache({
      // A 401 on /auth/me is the normal signed-out answer: RequireAuth and the landing page
      // handle it, and a first-time visitor must not be told their session ended.
      onError: (error, query) => {
        if (!isMe(query)) unauthenticated(error)
      },
      onSuccess: (_data, query) => {
        if (isMe(query)) signedOut = false
      },
    }),
    mutationCache: new MutationCache({
      // Signing out ends the session on purpose: requests still in flight answer 401, and that
      // is not an ended session to tell the user about.
      onMutate: (_variables, mutation) => {
        if (endsSession(mutation.options.meta)) signedOut = true
      },
      onError: (error, _variables, _result, mutation) => {
        if (endsSession(mutation.options.meta)) signedOut = false
        unauthenticated(error)
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: DERIVED_STALE_TIME_MS,
        retry: (failureCount, error) => failureCount < MAX_RETRIES && isRetryable(error),
        ...(retryDelay === undefined ? {} : { retryDelay }),
      },
      mutations: { retry: false },
    },
  })
  return queryClient
}
