import type { QueryClient } from '@tanstack/react-query'
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  COMPLETED_JOB,
  DEVELOPER_PROFILE,
  ME,
  NEVER_GENERATED,
  SYNCED_USER,
  callsTo,
  discoveryJob,
  json,
  mockFetch,
  noContent,
  renderRoute,
  unauthenticated,
} from '@/test/render'

const ME_ROUTE = { 'GET /api/v1/auth/me': () => json(ME) }

const generationJob = (status: string) => ({
  id: 9,
  job_type: 'recommendation_generation',
  status,
  steps: {},
})

/** Lets pending fetches and their follow-ups settle. */
const settle = () => act(() => new Promise((resolve) => setTimeout(resolve, 50)))

beforeEach(() => {
  document.cookie = 'csrftoken=test-csrf-token'
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('retry policy', () => {
  it('shows a 4xx at once, with one request', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/profile': () =>
        json({ error: { code: 'not_analyzed', message: 'Not built yet.' } }, 404),
    })
    renderRoute('/app')

    expect(await screen.findByText(/being prepared/i)).toBeInTheDocument()
    await settle()
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(1)
  })

  it('retries a server error', async () => {
    let calls = 0
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/profile': () => {
        calls += 1
        return calls === 1
          ? json({ error: { code: 'unavailable', message: 'Down.' } }, 503)
          : json(DEVELOPER_PROFILE)
      },
    })
    renderRoute('/app')

    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(2)
  })

  it('does not retry a 429', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/profile/skills?page_size=200': () =>
        json({ error: { code: 'throttled', message: 'Slow down.' } }, 429),
    })
    renderRoute('/app')

    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile/skills?page_size=200').length).toBe(1)
  })
})

describe('ended session', () => {
  it('returns to sign-in with a notice and drops cached data', async () => {
    let meCalls = 0
    mockFetch({
      ...SYNCED_USER,
      'GET /api/v1/auth/me': () => (meCalls++ === 0 ? json(ME) : unauthenticated()),
      'GET /api/v1/profile/github': unauthenticated,
    })
    const { router, queryClient } = renderRoute('/app')

    expect(await screen.findByRole('alert')).toHaveTextContent(/your session ended/i)
    expect(router.state.location.pathname).toBe('/')
    expect(screen.getByRole('link', { name: /continue with github/i })).toBeInTheDocument()
    await waitFor(() => expect(queryClient.getQueryData(['sync', 'status'])).toBeUndefined())
    expect(queryClient.getQueryData(['profile', 'github'])).toBeUndefined()
    expect(queryClient.getQueryCache().findAll({ queryKey: ['profile'] })).toHaveLength(0)
  })

  it('is not reported for a 401 that answers while the user logs out', async () => {
    let signedIn = true
    const rendered: { client?: QueryClient } = {}
    mockFetch({
      ...SYNCED_USER,
      'GET /api/v1/auth/me': () => (signedIn ? json(ME) : unauthenticated()),
      'GET /api/v1/sync/status': (init) =>
        signedIn ? SYNCED_USER['GET /api/v1/sync/status']!(init) : unauthenticated(),
      'POST /api/v1/auth/logout': async () => {
        signedIn = false
        // A poll that the ended session answers before the logout response arrives.
        await rendered.client!.refetchQueries({ queryKey: ['sync', 'status'] })
        return noContent()
      },
    })
    const { router, queryClient } = renderRoute('/app')
    rendered.client = queryClient
    const visited: string[] = []
    router.subscribe((state) => visited.push(state.location.search))

    await userEvent.click(await screen.findByRole('button', { name: /log out/i }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    await settle()
    expect(visited.filter((search) => search.includes('auth_error'))).toEqual([])
    expect(screen.queryByText(/your session ended/i)).not.toBeInTheDocument()
  })
})

describe('refresh on job transitions', () => {
  it('refetches only the status when coming back to the dashboard', async () => {
    const fetchMock = mockFetch({ ...ME_ROUTE, ...SYNCED_USER })
    const { router } = renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()
    const skills = callsTo(fetchMock, 'GET', '/api/v1/profile/skills?page_size=200').length
    const list = callsTo(fetchMock, 'GET', '/api/v1/recommendations').length

    await act(() => router.navigate('/privacy'))
    await act(() => router.navigate('/app'))
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/sync/status').length).toBe(2))
    await settle()

    expect(callsTo(fetchMock, 'GET', '/api/v1/profile/skills?page_size=200').length).toBe(skills)
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(list)
  })

  it('refetches profile data once when a sync finishes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let statusCalls = 0
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/sync/status': () =>
        statusCalls++ === 0
          ? json({
              job: { ...COMPLETED_JOB, id: 2, status: 'RUNNING', completed_at: null },
              last_synced_at: COMPLETED_JOB.completed_at,
            })
          : json({
              job: { ...COMPLETED_JOB, id: 2 },
              last_synced_at: COMPLETED_JOB.completed_at,
            }),
    })
    renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(1)

    await vi.advanceTimersByTimeAsync(2100)
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(2))
    await vi.advanceTimersByTimeAsync(5000)
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(2)
  })

  it('refetches the list once per finished generation, however many components show it', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let statusCalls = 0
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () =>
        json({
          ...NEVER_GENERATED,
          job: generationJob(statusCalls++ === 0 ? 'RUNNING' : 'COMPLETED'),
        }),
    })
    renderRoute('/app')
    // The list and the pipeline indicator both observe the generation status.
    expect(await screen.findByText('Preparing recommendations…')).toBeInTheDocument()
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(1)

    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(2))
    await vi.advanceTimersByTimeAsync(4000)
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(2)
  })

  it('refetches the profile once per finished generation, not the other statuses', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let statusCalls = 0
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () =>
        json({
          ...NEVER_GENERATED,
          job: generationJob(statusCalls++ === 0 ? 'RUNNING' : 'COMPLETED'),
        }),
    })
    const profileCalls = () =>
      [
        '/api/v1/profile',
        '/api/v1/profile/skills?page_size=200',
        '/api/v1/profile/interests?page_size=200',
      ].map((path) => callsTo(fetchMock, 'GET', path).length)
    renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()
    expect(profileCalls()).toEqual([1, 1, 1])
    const syncStatus = callsTo(fetchMock, 'GET', '/api/v1/sync/status').length
    const discoveryStatus = callsTo(fetchMock, 'GET', '/api/v1/discovery/status').length

    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() => expect(profileCalls()).toEqual([2, 2, 2]))
    await vi.advanceTimersByTimeAsync(4000)
    expect(profileCalls()).toEqual([2, 2, 2])
    expect(callsTo(fetchMock, 'GET', '/api/v1/sync/status').length).toBe(syncStatus)
    expect(callsTo(fetchMock, 'GET', '/api/v1/discovery/status').length).toBe(discoveryStatus)
  })

  it('looks for the generation once when discovery finishes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let discoveryCalls = 0
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/discovery/status': () =>
        json({
          job: discoveryJob(discoveryCalls++ === 0 ? 'RUNNING' : 'COMPLETED'),
          last_completed_at: null,
          pool: { total: 0, eligible: 0, awaiting_analysis: 0, ineligible: 0, by_source: {} },
        }),
    })
    renderRoute('/app')
    expect(await screen.findByText('Finding projects…')).toBeInTheDocument()
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations/status').length).toBe(1)

    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() =>
      expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations/status').length).toBe(2),
    )
    await vi.advanceTimersByTimeAsync(4000)
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations/status').length).toBe(2)
  })
})
