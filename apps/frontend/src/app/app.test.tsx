import { focusManager, type QueryClient } from '@tanstack/react-query'
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createQueryClient } from '@/app/queryClient'
import {
  COMPLETED_JOB,
  DEVELOPER_PROFILE,
  ME,
  NEVER_GENERATED,
  SYNCED_USER,
  callsTo,
  changingVersions,
  discoveryJob,
  json,
  mockFetch,
  noContent,
  renderRoute,
  unauthenticated,
  type FetchMock,
} from '@/test/render'

const ME_ROUTE = { 'GET /api/v1/auth/me': () => json(ME) }

const generationJob = (status: string) => ({
  id: 9,
  job_type: 'recommendation_generation',
  status,
  steps: {},
})

const profileCalls = (fetchMock: FetchMock) =>
  [
    '/api/v1/profile',
    '/api/v1/profile/skills?page_size=200',
    '/api/v1/profile/interests?page_size=200',
  ].map((path) => callsTo(fetchMock, 'GET', path).length)

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

  it('does not retry a success body that is not JSON', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/profile/skills?page_size=200': () =>
        new Response('<html>app</html>', { status: 200 }),
    })
    renderRoute('/app')

    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile/skills?page_size=200').length).toBe(1)
  })

  it('retries a request that got no response, twice', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/profile/skills?page_size=200': () => {
        throw new TypeError('Failed to fetch')
      },
    })
    renderRoute('/app')

    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile/skills?page_size=200').length).toBe(3)
  })

  it('does not retry an error that is not an ApiError', async () => {
    const queryClient = createQueryClient({ retryDelay: 0, navigate: async () => undefined })
    const queryFn = vi.fn(() => Promise.reject(new SyntaxError('bug')))
    await expect(queryClient.fetchQuery({ queryKey: ['bug'], queryFn })).rejects.toThrow('bug')
    expect(queryFn).toHaveBeenCalledTimes(1)
  })
})

describe('refresh by data versions', () => {
  it('refetches nothing on the first fetch', async () => {
    const fetchMock = mockFetch({ ...ME_ROUTE, ...SYNCED_USER })
    renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()
    expect(callsTo(fetchMock, 'GET', '/api/v1/sync/versions').length).toBe(1)
    expect(profileCalls(fetchMock)).toEqual([1, 1, 1])
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(1)
  })

  it('refetches only the recommendations after a background repository refresh', async () => {
    const versions = changingVersions()
    const fetchMock = mockFetch({ ...ME_ROUTE, ...SYNCED_USER, ...versions.route })
    const { router } = renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()

    versions.change('recommendations')
    await act(() => router.navigate('/app#recommendations'))
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(2))
    await settle()
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(2)
    expect(profileCalls(fetchMock)).toEqual([1, 1, 1])
  })

  it('refetches only the profile on focus after an analysis whose discovery failed', async () => {
    const versions = changingVersions()
    const fetchMock = mockFetch({ ...ME_ROUTE, ...SYNCED_USER, ...versions.route })
    renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()

    versions.change('profile')
    act(() => {
      focusManager.setFocused(false)
      focusManager.setFocused(true)
    })
    try {
      await waitFor(() => expect(profileCalls(fetchMock)).toEqual([2, 2, 2]))
      await settle()
      expect(profileCalls(fetchMock)).toEqual([2, 2, 2])
      expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(1)
    } finally {
      focusManager.setFocused(undefined)
    }
  })

  it('refetches nothing when switching pages with unchanged versions', async () => {
    const fetchMock = mockFetch({ ...ME_ROUTE, ...SYNCED_USER })
    const { router } = renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()

    await act(() => router.navigate('/app#recommendations'))
    await settle()
    await act(() => router.navigate('/app'))
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/sync/versions').length).toBe(3))
    await settle()
    expect(profileCalls(fetchMock)).toEqual([1, 1, 1])
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(1)
  })

  it('refetches nothing when a versions fetch fails', async () => {
    let fail = false
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/sync/versions': () =>
        fail
          ? json({ error: { code: 'server_error', message: 'Down.' } }, 500)
          : json({ github: null, profile: null, recommendations: null }),
    })
    const { router } = renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()

    fail = true
    await act(() => router.navigate('/app#recommendations'))
    // The first fetch plus one failed fetch with its two retries.
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/sync/versions').length).toBe(4))
    await settle()
    expect(profileCalls(fetchMock)).toEqual([1, 1, 1])
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(1)
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

  it('refetches what a finished sync changed, once', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let statusCalls = 0
    const versions = changingVersions()
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      ...versions.route,
      'GET /api/v1/sync/status': () => {
        if (statusCalls++ === 0) {
          return json({
            job: { ...COMPLETED_JOB, id: 2, status: 'RUNNING', completed_at: null },
            last_synced_at: COMPLETED_JOB.completed_at,
          })
        }
        if (statusCalls === 2) versions.change('github', 'profile')
        return json({
          job: { ...COMPLETED_JOB, id: 2 },
          last_synced_at: COMPLETED_JOB.completed_at,
        })
      },
    })
    renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(1)
    const list = callsTo(fetchMock, 'GET', '/api/v1/recommendations').length

    await vi.advanceTimersByTimeAsync(2100)
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(2))
    await vi.advanceTimersByTimeAsync(5000)
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(2)
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile/github').length).toBe(2)
    expect(callsTo(fetchMock, 'GET', '/api/v1/sync/versions').length).toBe(2)
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(list)
  })

  it('keeps polling a stalled sync without refreshing, then refreshes once when it finishes', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let statusCalls = 0
    const versions = changingVersions()
    const running = { ...COMPLETED_JOB, id: 2, status: 'RUNNING', completed_at: null }
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      ...versions.route,
      'GET /api/v1/sync/status': () => {
        statusCalls += 1
        // Stalled twice, resumed once, then finished.
        const job =
          statusCalls <= 2
            ? { ...running, stalled: true }
            : statusCalls === 3
              ? running
              : { ...COMPLETED_JOB, id: 2 }
        if (statusCalls === 4) versions.change('github', 'profile')
        return json({ job, last_synced_at: COMPLETED_JOB.completed_at })
      },
    })
    renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()

    await vi.advanceTimersByTimeAsync(2100)
    await waitFor(() => expect(statusCalls).toBeGreaterThanOrEqual(2))
    expect(callsTo(fetchMock, 'GET', '/api/v1/sync/versions').length).toBe(1)
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(1)

    await vi.advanceTimersByTimeAsync(4200)
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(2))
    await vi.advanceTimersByTimeAsync(5000)
    expect(callsTo(fetchMock, 'GET', '/api/v1/profile').length).toBe(2)
    expect(callsTo(fetchMock, 'GET', '/api/v1/sync/versions').length).toBe(2)
  })

  it('refetches the list once per finished generation, however many components show it', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let statusCalls = 0
    const versions = changingVersions()
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      ...versions.route,
      'GET /api/v1/recommendations/status': () => {
        if (statusCalls++ === 1) versions.change('recommendations')
        return json({
          ...NEVER_GENERATED,
          job: generationJob(statusCalls === 1 ? 'RUNNING' : 'COMPLETED'),
        })
      },
    })
    renderRoute('/app')
    // The list and the pipeline indicator both observe the generation status.
    expect(await screen.findByText('Preparing recommendations…')).toBeInTheDocument()
    await settle()
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(1)
    expect(callsTo(fetchMock, 'GET', '/api/v1/sync/versions').length).toBe(1)

    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(2))
    await vi.advanceTimersByTimeAsync(4000)
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(2)
    expect(callsTo(fetchMock, 'GET', '/api/v1/sync/versions').length).toBe(2)
  })

  it('leaves the profile alone after a generation without a profile change', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let statusCalls = 0
    const versions = changingVersions()
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      ...versions.route,
      'GET /api/v1/recommendations/status': () => {
        if (statusCalls++ === 1) versions.change('recommendations')
        return json({
          ...NEVER_GENERATED,
          job: generationJob(statusCalls === 1 ? 'RUNNING' : 'COMPLETED'),
        })
      },
    })
    renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()
    expect(profileCalls(fetchMock)).toEqual([1, 1, 1])
    const syncStatus = callsTo(fetchMock, 'GET', '/api/v1/sync/status').length
    const discoveryStatus = callsTo(fetchMock, 'GET', '/api/v1/discovery/status').length

    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(2))
    await vi.advanceTimersByTimeAsync(4000)
    expect(profileCalls(fetchMock)).toEqual([1, 1, 1])
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
    // Discovery changes no data area: the versions wait for the generation (U-5).
    expect(callsTo(fetchMock, 'GET', '/api/v1/sync/versions').length).toBe(1)
  })

  it('refetches each changed area once when two jobs finish together', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let syncCalls = 0
    let generationCalls = 0
    const versions = changingVersions()
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      ...versions.route,
      'GET /api/v1/sync/status': () => {
        if (syncCalls++ === 0) {
          return json({
            job: { ...COMPLETED_JOB, id: 2, status: 'RUNNING', completed_at: null },
            last_synced_at: COMPLETED_JOB.completed_at,
          })
        }
        versions.change('github', 'profile', 'recommendations')
        return json({
          job: { ...COMPLETED_JOB, id: 2 },
          last_synced_at: COMPLETED_JOB.completed_at,
        })
      },
      'GET /api/v1/recommendations/status': () =>
        json({
          ...NEVER_GENERATED,
          job: generationJob(generationCalls++ === 0 ? 'RUNNING' : 'COMPLETED'),
        }),
    })
    renderRoute('/app')
    expect(await screen.findByText(DEVELOPER_PROFILE.summary)).toBeInTheDocument()
    await settle()
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(1)

    // Both statuses poll (2 s and 3 s) and see their job finished before the versions answer.
    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() => expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(2))
    await vi.advanceTimersByTimeAsync(5000)
    expect(callsTo(fetchMock, 'GET', '/api/v1/recommendations').length).toBe(2)
    expect(profileCalls(fetchMock)).toEqual([2, 2, 2])
  })
})
