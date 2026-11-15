import type { ReactNode } from 'react'

import { DeadEnd } from './DeadEnd'
import { Loading } from './Loading'

type QueryState<T> = { data: T | undefined; isError: boolean; isFetching?: boolean }

/** A first load that failed and is not being retried. */
const failedFirstLoad = (query: QueryState<unknown>) => query.isError && !query.isFetching

/** A query's content in the one page order: the data once loaded (also after a failed refetch,
 * which keeps what is shown), else `failed` for a first load that failed (never an empty list),
 * else `loading`, also while a failed first load is retried (CMP-5). */
export function Loaded<T>({
  query,
  failed,
  loading = <Loading />,
  children,
}: {
  query: QueryState<T>
  failed: ReactNode
  loading?: ReactNode
  children: (data: T) => ReactNode
}) {
  if (query.data !== undefined) return children(query.data)
  return failedFirstLoad(query) ? failed : loading
}

/** A detail page's gate (CMP-7): a 404 is the `gone` dead end, also over data already shown
 * (the thing left); else the data (kept after a failed refetch); else the `failed` dead end
 * with "Try again" for a failed first load; else loading. */
export function DetailLoaded<T>({
  query,
  gone,
  failed,
  children,
}: {
  query: QueryState<T> & { error: { status?: number } | null; refetch: () => unknown }
  gone: string
  failed: string
  children: (data: T) => ReactNode
}) {
  if (query.error?.status === 404) return <DeadEnd message={gone} />
  if (query.data !== undefined) return children(query.data)
  if (failedFirstLoad(query))
    return <DeadEnd message={failed} onRetry={() => void query.refetch()} />
  return <Loading />
}
