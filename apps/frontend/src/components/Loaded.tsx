import type { ReactNode } from 'react'

/** A query's content in the one page order: the data once loaded (also after a failed refetch,
 * which keeps what is shown), else `failed` for a first load that failed (never an empty list),
 * else `loading`. */
export function Loaded<T>({
  query,
  failed,
  loading = <p className="text-muted-foreground text-sm">Loading…</p>,
  children,
}: {
  query: { data: T | undefined; isError: boolean }
  failed: ReactNode
  loading?: ReactNode
  children: (data: T) => ReactNode
}) {
  if (query.data !== undefined) return children(query.data)
  return query.isError ? failed : loading
}
