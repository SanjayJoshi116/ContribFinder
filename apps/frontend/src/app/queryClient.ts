import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/api/client'

import { ENDS_SESSION_META_KEY, type Navigate, endSession, isMe, meQueryKey } from './session'

const MAX_RETRIES = 2

/** Data derived from jobs changes only when a job finishes (the status queries refresh it)
 * or through the user's own actions (their mutations refresh it), so it is not refetched on
 * every mount or focus. Status queries set `staleTime: 0`. */
const DERIVED_STALE_TIME_MS = 5 * 60_000

/** Only failures a retry can fix: no response (`network_error`) or a server error. A 4xx is
 * the answer, and retrying it only delays showing it; an unreadable success body or a bug in a
 * query function would fail the same way again. */
function isRetryable(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 0 || error.status >= 500)
}

function endsSession(meta: Record<string, unknown> | undefined): boolean {
  return meta?.[ENDS_SESSION_META_KEY] === true
}

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
    // A failed navigation must not leave later 401s ignored (APP-6). `endSession` has already
    // removed the identity; putting it back keeps the signed-in pages, and the next 401 on it
    // ends the session with the notice again (CR-7).
    const me = queryClient.getQueryData(meQueryKey)
    endSession(queryClient, navigate).catch(() => {
      signedOut = false
      if (me !== undefined) queryClient.setQueryData(meQueryKey, me)
    })
  }

  const queryClient = new QueryClient({
    queryCache: new QueryCache({
      // A 401 on /auth/me is the normal signed-out answer (RequireAuth and the landing page
      // handle it, and a first-time visitor must not be told their session ended), unless the
      // identity was known: then the session ended.
      onError: (error, query) => {
        if (!isMe(query) || query.state.data !== undefined) unauthenticated(error)
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
        if (endsSession(mutation.options.meta)) {
          signedOut = false
          // 401s were ignored while it was pending: ask whether the session is still there; a
          // 401 on the known identity ends it through the query cache above (APP-5).
          if (!(error instanceof ApiError && error.status === 401)) {
            void queryClient.refetchQueries({ queryKey: meQueryKey, exact: true })
          }
        }
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
