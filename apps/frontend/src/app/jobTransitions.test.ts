import { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SyncJob } from '@/api/types'
import { COMPLETED_JOB, json } from '@/test/render'

import { fetchStatusAndRefresh } from './jobTransitions'

const KEY = ['sync', 'status']
const PATH = '/sync/status'

const job = (id: number, status: SyncJob['status']) =>
  ({ ...COMPLETED_JOB, id, status }) as unknown as SyncJob

type Status = { job: SyncJob | null }

/** Stubs `fetch` with one answer per call; each answer is a status, or a held one that answers
 * when released and rejects like `fetch` once aborted (unless it ignores the signal, like a
 * response that resolved just before the abort). */
function stubFetch(...answers: (Status | ReturnType<typeof held>)[]) {
  const signals: AbortSignal[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      signals.push(init!.signal!)
      const answer = answers.shift()!
      return 'release' in answer ? answer.respond(init!.signal!) : json(answer)
    }),
  )
  return signals
}

function held(status: Status, { ignoreAbort = false } = {}) {
  let release = () => {}
  return {
    release: () => release(),
    respond: (signal: AbortSignal) =>
      new Promise<Response>((resolve, reject) => {
        release = () => resolve(json(status))
        if (!ignoreAbort) {
          signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        }
      }),
  }
}

function clientWith(previous: Status) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(KEY, previous)
  return queryClient
}

const run = (queryClient: QueryClient, refresh: () => Promise<unknown>) =>
  queryClient.fetchQuery({
    queryKey: KEY,
    queryFn: ({ signal }) => fetchStatusAndRefresh<Status>(queryClient, KEY, PATH, signal, refresh),
    staleTime: 0,
  })

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchStatusAndRefresh', () => {
  it('refreshes once for a newly finished job', async () => {
    const queryClient = clientWith({ job: job(5, 'RUNNING') })
    const refresh = vi.fn(async () => {})
    stubFetch({ job: job(5, 'COMPLETED') })

    await run(queryClient, refresh)

    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('refreshes nothing when the job is gone (data deleted)', async () => {
    const queryClient = clientWith({ job: job(5, 'COMPLETED') })
    const refresh = vi.fn(async () => {})
    stubFetch({ job: null })

    await run(queryClient, refresh)

    expect(refresh).not.toHaveBeenCalled()
  })

  it('refreshes once when a fetch is cancelled and fetched again', async () => {
    const queryClient = clientWith({ job: job(5, 'RUNNING') })
    const refresh = vi.fn(async () => {})
    stubFetch(held({ job: job(5, 'COMPLETED') }), { job: job(5, 'COMPLETED') })

    const abandoned = run(queryClient, refresh).catch(() => undefined)
    await queryClient.cancelQueries({ queryKey: KEY })
    await abandoned
    await run(queryClient, refresh)

    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('refreshes nothing for an answer that arrives after its fetch was cancelled', async () => {
    const queryClient = clientWith({ job: job(5, 'RUNNING') })
    const refresh = vi.fn(async () => {})
    const late = held({ job: job(5, 'COMPLETED') }, { ignoreAbort: true })
    const signals = stubFetch(late)

    const pending = run(queryClient, refresh).catch(() => undefined)
    await vi.waitFor(() => expect(signals).toHaveLength(1))
    await queryClient.cancelQueries({ queryKey: KEY })
    expect(signals[0]!.aborted).toBe(true)
    late.release()
    await pending
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(refresh).not.toHaveBeenCalled()
  })
})
