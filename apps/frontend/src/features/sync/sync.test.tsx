import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  COMPLETED_JOB,
  ME,
  REPO,
  SYNCED_USER,
  callsTo,
  json,
  mockFetch,
  renderRoute,
} from '@/test/render'

const ME_ROUTE = { 'GET /api/v1/auth/me': () => json(ME) }
const NEVER_SYNCED = { 'GET /api/v1/sync/status': () => json({ job: null, last_synced_at: null }) }

function job(overrides: Record<string, unknown>) {
  return { ...COMPLETED_JOB, completed_at: null, ...overrides }
}

beforeEach(() => {
  document.cookie = 'csrftoken=test-csrf-token'
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('app redirect', () => {
  it('sends never-synced users to onboarding', async () => {
    mockFetch({ ...ME_ROUTE, ...NEVER_SYNCED })
    const { router } = renderRoute('/app')

    await waitFor(() => expect(router.state.location.pathname).toBe('/onboarding'))
    expect(await screen.findByRole('button', { name: /start sync/i })).toBeInTheDocument()
  })
})

describe('onboarding', () => {
  it(
    'shows step progress and moves to the app when the sync completes',
    { timeout: 10_000 },
    async () => {
      let polls = 0
      mockFetch({
        ...ME_ROUTE,
        ...SYNCED_USER,
        'GET /api/v1/sync/status': () => {
          polls += 1
          return polls === 1
            ? json({
                job: job({
                  status: 'RUNNING',
                  steps: { profile: 'done', readme: 'not_found', repositories: 'running' },
                }),
                last_synced_at: null,
              })
            : json({ job: COMPLETED_JOB, last_synced_at: COMPLETED_JOB.completed_at })
        },
      })
      const { router } = renderRoute('/onboarding')

      const steps = await screen.findByRole('list', { name: /sync progress/i })
      const items = within(steps).getAllByRole('listitem')
      expect(items.map((li) => li.getAttribute('data-state'))).toEqual([
        'done',
        'not_found',
        'running',
        'pending',
        'pending',
        'pending',
        'pending',
        'pending',
      ])
      expect(within(items[7]).getByText('Building profile')).toBeInTheDocument()
      expect(within(items[1]).getByText('Not found')).toBeInTheDocument()

      // The next poll (every 2 s) reports COMPLETED.
      await waitFor(() => expect(router.state.location.pathname).toBe('/app'), { timeout: 5000 })
      expect(
        await screen.findByRole('heading', { name: /welcome, the octocat/i }),
      ).toBeInTheDocument()
    },
  )

  it('asks to sign in again when GitHub access is invalid', async () => {
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/sync/status': () =>
        json({
          job: job({ status: 'FAILED', error_code: 'github_auth_invalid' }),
          last_synced_at: null,
        }),
    })
    renderRoute('/onboarding')

    expect(await screen.findByRole('alert')).toHaveTextContent(/expired or was revoked/i)
    expect(screen.getByRole('link', { name: /sign in with github again/i })).toHaveAttribute(
      'href',
      '/api/v1/auth/github',
    )
    expect(screen.queryByRole('button', { name: /try again/i })).not.toBeInTheDocument()
  })

  it('offers a retry for other failures and starts a new sync', async () => {
    let started = false
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/sync/status': () =>
        json({
          job: started
            ? job({ id: 2, status: 'PENDING', steps: {} })
            : job({ status: 'FAILED', error_code: 'github_unavailable' }),
          last_synced_at: null,
        }),
      'POST /api/v1/profile/sync': () => {
        started = true
        return json(job({ id: 2, status: 'PENDING', steps: {} }), 202)
      },
    })
    renderRoute('/onboarding')

    expect(await screen.findByRole('alert')).toHaveTextContent(/not responding/i)
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) => url === '/api/v1/profile/sync' && init?.method === 'POST',
        ),
      ).toBe(true),
    )
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })

  it('says a stalled sync stopped and offers to try again', async () => {
    let started = false
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/sync/status': () =>
        json({
          job: started
            ? job({ id: 2, status: 'PENDING', steps: {} })
            : job({ status: 'RUNNING', steps: { profile: 'running' }, stalled: true }),
          last_synced_at: null,
        }),
      'POST /api/v1/profile/sync': () => {
        started = true
        return json(job({ id: 2, status: 'PENDING', steps: {} }), 202)
      },
    })
    renderRoute('/onboarding')

    expect(await screen.findByText(/Background work stopped/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /try again/i }))
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/profile/sync')).toHaveLength(1))
    await waitFor(() =>
      expect(screen.queryByText(/Background work stopped/)).not.toBeInTheDocument(),
    )
  })

  it('explains automatic retries while RETRYING', async () => {
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/sync/status': () =>
        json({
          job: job({ status: 'RETRYING', steps: { profile: 'failed' } }),
          last_synced_at: null,
        }),
    })
    renderRoute('/onboarding')
    expect(await screen.findByText(/retrying automatically/i)).toBeInTheDocument()
  })
})

describe('dashboard', () => {
  it('shows profile, repositories and last-synced time', async () => {
    mockFetch({ ...ME_ROUTE, ...SYNCED_USER })
    renderRoute('/app')

    expect(
      await screen.findByRole('heading', { name: /welcome, the octocat/i }),
    ).toBeInTheDocument()
    expect(await screen.findByText('Builds tools')).toBeInTheDocument()
    expect(screen.getByText(/last synced/i)).toBeInTheDocument()
    const repos = screen.getByRole('list', { name: 'Repositories' })
    expect(within(repos).getByRole('link', { name: 'octocat/tools' })).toHaveAttribute(
      'href',
      'https://github.com/octocat/tools',
    )
    expect(within(repos).getByText('cli')).toBeInTheDocument()
  })

  it('lists repositories from every page', async () => {
    const repo = (name: string) => ({
      ...REPO,
      id: 100 + name.length,
      name,
      full_name: `octocat/${name}`,
      html_url: `https://github.com/octocat/${name}`,
    })
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/profile/repositories?page_size=100': () =>
        json({
          count: 2,
          next: 'http://testserver/api/v1/profile/repositories?page=2&page_size=100',
          previous: null,
          results: [repo('first')],
        }),
      'GET /api/v1/profile/repositories?page=2&page_size=100': () =>
        json({ count: 2, next: null, previous: null, results: [repo('second')] }),
    })
    renderRoute('/app')

    const repos = await screen.findByRole('list', { name: 'Repositories' })
    expect(await within(repos).findByRole('link', { name: 'octocat/second' })).toBeInTheDocument()
    expect(within(repos).getByRole('link', { name: 'octocat/first' })).toBeInTheDocument()
    expect(
      callsTo(fetchMock, 'GET', '/api/v1/profile/repositories?page=2&page_size=100'),
    ).toHaveLength(1)
  })

  it('refresh starts a sync', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'POST /api/v1/profile/sync': () => json(job({ id: 3, status: 'PENDING', steps: {} }), 202),
    })
    renderRoute('/app')

    await userEvent.click(await screen.findByRole('button', { name: /refresh/i }))

    expect(await screen.findByRole('status')).toHaveTextContent('Syncing GitHub data…')
    expect(screen.getByRole('button', { name: /refresh/i })).toBeDisabled()
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(new Headers(post[1]!.headers).get('X-CSRFToken')).toBe('test-csrf-token')
  })

  it('explains the cooldown using Retry-After', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'POST /api/v1/profile/sync': () =>
        new Response(
          JSON.stringify({ error: { code: 'sync_cooldown', message: 'A sync ran recently.' } }),
          { status: 429, headers: { 'Content-Type': 'application/json', 'Retry-After': '240' } },
        ),
    })
    renderRoute('/app')

    await userEvent.click(await screen.findByRole('button', { name: /refresh/i }))

    expect(await screen.findByRole('status')).toHaveTextContent(
      /you can refresh again in 4 minutes/i,
    )
  })
})
