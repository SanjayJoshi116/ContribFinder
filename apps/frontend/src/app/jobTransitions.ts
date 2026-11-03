import type { QueryClient, QueryKey } from '@tanstack/react-query'

import { apiFetch } from '@/api/client'
import type { SyncJob } from '@/api/types'

const ACTIVE: ReadonlySet<SyncJob['status']> = new Set(['PENDING', 'RUNNING', 'RETRYING'])

export function isActive(job: SyncJob | null | undefined): boolean {
  return !!job && ACTIVE.has(job.status)
}

/** Running, but its worker stopped sending heartbeats (the server sets `stalled` only for a
 * RUNNING job). Still active: it is polled and never treated as finished (recovery resumes
 * it), but the user may start a sync over it. */
export function isStalled(job: SyncJob | null | undefined): boolean {
  return !!job?.stalled
}

const jobKey = (job: SyncJob | null | undefined) => `${job?.id ?? ''}:${job?.status ?? ''}`

/** Fetches the job status at `path` and refreshes what the job produces once it has finished.
 *
 * Runs inside the status query's `queryFn`, so it runs once per fetch however many components
 * show the status. It compares with the cached previous status: seeing the same finished job
 * again (focus, remount) refreshes nothing, and a job that started and finished between two
 * fetches still has a new id. Without a previous status the derived data is loading for the
 * first time anyway, and a status without a job (the user's data was deleted) finished nothing.
 * The request carries the query's `signal`: a cancelled fetch (a refetch of the same status, or
 * leaving the signed-in pages) stops before comparing, so only the fetch that replaces it can
 * refresh (APP-2, APP-3). The refresh is started, not awaited: the status must not wait on (or
 * hang with) the derived refetches, which can include other status queries. */
export async function fetchStatusAndRefresh<S extends { job?: SyncJob | null }>(
  queryClient: QueryClient,
  key: QueryKey,
  path: string,
  signal: AbortSignal,
  refresh: () => Promise<unknown>,
): Promise<S> {
  const previous = queryClient.getQueryData<S>(key)
  const status = await apiFetch<S>(path, { signal })
  if (
    !signal.aborted &&
    previous !== undefined &&
    status.job &&
    jobKey(previous.job) !== jobKey(status.job) &&
    !isActive(status.job)
  ) {
    void refresh()
  }
  return status
}
