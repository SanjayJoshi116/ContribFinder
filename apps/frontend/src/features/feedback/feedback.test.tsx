import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  COMPLETED_JOB,
  ME,
  NEVER_DISCOVERED,
  SYNCED_USER,
  discoveryJob,
  json,
  mockFetch,
  noContent,
  renderRoute,
  unauthenticated,
} from '@/test/render'

const ME_ROUTE = { 'GET /api/v1/auth/me': () => json(ME) }

const REPOSITORY = {
  full_name: 'encode/httpx',
  owner: 'encode',
  name: 'httpx',
  description: 'A next generation HTTP client for Python.',
  html_url: 'https://github.com/encode/httpx',
  primary_language: 'Python',
  stars: 13000,
  topics: ['python'],
  license: 'BSD-3-Clause',
}

const RECOMMENDATION = {
  id: 7,
  repository_id: 70,
  repository: REPOSITORY,
  match_label: 'strong',
  technologies: [{ slug: 'python', name: 'Python', category: 'language', matched: true }],
  reasons: [{ type: 'skill', text: 'Shares Python with your profile', detail: {} }],
  activity_label: 'recently_active',
  size: 'large',
  openness: {
    contributing: true,
    code_of_conduct: null,
    issue_templates: null,
    pull_request_template: null,
    good_first_issue: null,
    help_wanted: null,
  },
  saved: false,
  relevant_issue_count: 0,
  generated_at: '2026-09-29T10:00:00Z',
}

const DETAIL = {
  ...RECOMMENDATION,
  languages: [{ language: 'Python', share: 1 }],
  issues: [],
  readme_excerpt: '',
  activity_signals: null,
}

const GENERATED = {
  job: { id: 9, job_type: 'recommendation_generation', status: 'COMPLETED', steps: {} },
  last_generated_at: '2026-09-29T10:00:00Z',
  count: 1,
  config_version: 'v1-deterministic',
}

const page = (results: unknown[]) =>
  json({ count: results.length, next: null, previous: null, results })

const WITH_RECOMMENDATION = {
  ...ME_ROUTE,
  ...SYNCED_USER,
  'GET /api/v1/recommendations/status': () => json(GENERATED),
  'GET /api/v1/recommendations': () => page([RECOMMENDATION]),
}

type Calls = ReturnType<typeof mockFetch>['mock']['calls']
const callsTo = (calls: Calls, method: string, url: string) =>
  calls.filter(([u, init]) => u === url && (init?.method ?? 'GET').toUpperCase() === method)

beforeEach(() => {
  document.cookie = 'csrftoken=test-csrf-token'
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('save and dismiss', () => {
  it('toggles Save to Saved without a reload', async () => {
    const fetchMock = mockFetch({
      ...WITH_RECOMMENDATION,
      'POST /api/v1/recommendations/7/save': () => json({ saved: true }),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })

    await userEvent.click(within(card).getByRole('button', { name: 'Save' }))

    const saved = await within(card).findByRole('button', { name: 'Saved' })
    expect(saved).toHaveAttribute('aria-pressed', 'true')
    expect(callsTo(fetchMock.mock.calls, 'POST', '/api/v1/recommendations/7/save')).toHaveLength(1)
  })

  it('rolls Save back when the request fails', async () => {
    mockFetch({
      ...WITH_RECOMMENDATION,
      'POST /api/v1/recommendations/7/save': () =>
        json({ error: { code: 'error', message: 'Nope' } }, 500),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })
    await userEvent.click(within(card).getByRole('button', { name: 'Save' }))
    expect(await within(card).findByRole('button', { name: 'Save' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('removes a dismissed card at once, and Undo restores it', async () => {
    let dismissed = false
    // Answer the dismissal only after the card is gone, as on a real network: the button that
    // started it has unmounted by then.
    let answerDismiss: () => void = () => {}
    const fetchMock = mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () => page(dismissed ? [] : [RECOMMENDATION]),
      'POST /api/v1/recommendations/7/dismiss': () =>
        new Promise<Response>((resolve) => {
          answerDismiss = () => {
            dismissed = true
            resolve(noContent())
          }
        }),
      'DELETE /api/v1/dismissed/70': () => noContent(),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })

    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }))

    await waitFor(() =>
      expect(screen.queryByRole('article', { name: 'httpx' })).not.toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(
        callsTo(fetchMock.mock.calls, 'POST', '/api/v1/recommendations/7/dismiss'),
      ).toHaveLength(1),
    )
    answerDismiss()
    const notice = await screen.findByText(/hidden encode\/httpx/i)
    await userEvent.click(within(notice.parentElement!).getByRole('button', { name: 'Undo' }))

    await waitFor(() =>
      expect(callsTo(fetchMock.mock.calls, 'DELETE', '/api/v1/dismissed/70')).toHaveLength(1),
    )
    await waitFor(() => expect(screen.queryByText(/hidden encode\/httpx/i)).not.toBeInTheDocument())
  })

  it('dismisses from the detail page and offers Undo on the dashboard', async () => {
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations/7': () => json(DETAIL),
      'POST /api/v1/recommendations/7/feedback': () => noContent(),
      'POST /api/v1/recommendations/7/dismiss': () => noContent(),
    })
    const { router } = renderRoute('/app/recommendations/7')
    await userEvent.click(await screen.findByRole('button', { name: 'Dismiss' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/app'))
    expect(await screen.findByText(/hidden encode\/httpx/i)).toBeInTheDocument()
  })
})

describe('interaction events', () => {
  it('records one view when the detail page opens', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/recommendations/7': () => json(DETAIL),
      'POST /api/v1/recommendations/7/feedback': () => noContent(),
    })
    renderRoute('/app/recommendations/7')
    await screen.findByRole('heading', { name: 'encode/httpx' })

    await waitFor(() =>
      expect(
        callsTo(fetchMock.mock.calls, 'POST', '/api/v1/recommendations/7/feedback'),
      ).toHaveLength(1),
    )
    const [, init] = callsTo(fetchMock.mock.calls, 'POST', '/api/v1/recommendations/7/feedback')[0]!
    expect(JSON.parse(init!.body as string)).toEqual({ action: 'viewed' })
    expect(init!.keepalive).toBe(true)
  })

  it('records opening on GitHub without blocking the link, and hides failures', async () => {
    const fetchMock = mockFetch({
      ...WITH_RECOMMENDATION,
      'POST /api/v1/recommendations/7/feedback': () =>
        json({ error: { code: 'error', message: 'down' } }, 500),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })
    const link = within(card).getByRole('link', { name: 'Open on GitHub' })
    expect(link).toHaveAttribute('href', 'https://github.com/encode/httpx')
    expect(link).toHaveAttribute('target', '_blank')

    await userEvent.click(link)

    await waitFor(() => {
      const posts = callsTo(fetchMock.mock.calls, 'POST', '/api/v1/recommendations/7/feedback')
      expect(posts).toHaveLength(1)
      expect(JSON.parse(posts[0]![1]!.body as string)).toEqual({ action: 'opened_repository' })
    })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('saved projects page', () => {
  it('lists saved projects, marks the ones no longer recommended, and restores hidden ones', async () => {
    let hidden = true
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/saved?page_size=100': () =>
        page([
          {
            repository_id: 70,
            repository: REPOSITORY,
            saved_at: '2026-09-29T10:00:00Z',
            activity_label: 'recently_active',
            recommendation: { id: 7, match_label: 'strong', reasons: RECOMMENDATION.reasons },
          },
          {
            repository_id: 71,
            repository: { ...REPOSITORY, full_name: 'old/project', name: 'project' },
            saved_at: '2026-09-20T10:00:00Z',
            activity_label: '',
            recommendation: null,
          },
        ]),
      'GET /api/v1/dismissed?page_size=100': () =>
        page(
          hidden
            ? [
                {
                  repository_id: 72,
                  repository: { ...REPOSITORY, full_name: 'meh/thing', name: 'thing' },
                  dismissed_at: '2026-09-29T11:00:00Z',
                },
              ]
            : [],
        ),
      'DELETE /api/v1/dismissed/72': () => {
        hidden = false
        return noContent()
      },
    })
    renderRoute('/app/saved')

    const current = await screen.findByRole('article', { name: 'encode/httpx' })
    expect(within(current).getByText('Strong match')).toBeInTheDocument()
    expect(within(current).getByRole('link', { name: 'encode/httpx' })).toHaveAttribute(
      'href',
      '/app/recommendations/7',
    )
    const old = screen.getByRole('article', { name: 'old/project' })
    expect(within(old).getByText(/no longer recommended/i)).toBeInTheDocument()
    expect(within(old).queryByText(/match/i)).not.toBeInTheDocument()

    const hiddenList = await screen.findByRole('list', { name: 'Hidden projects' })
    await userEvent.click(within(hiddenList).getByRole('button', { name: 'Restore' }))
    expect(await screen.findByText('No hidden projects.')).toBeInTheDocument()
    expect(callsTo(fetchMock.mock.calls, 'DELETE', '/api/v1/dismissed/72')).toHaveLength(1)
  })

  it('is linked from the dashboard', async () => {
    mockFetch(WITH_RECOMMENDATION)
    renderRoute('/app')
    expect(await screen.findByRole('link', { name: 'Saved and hidden projects' })).toHaveAttribute(
      'href',
      '/app/saved',
    )
  })
})

describe('pipeline stage line', () => {
  const running = (steps: Record<string, string>) => ({
    ...COMPLETED_JOB,
    id: 5,
    status: 'RUNNING',
    steps: { ...COMPLETED_JOB.steps, ...steps },
    completed_at: null,
  })

  it.each([
    ['syncing', running({ repositories: 'running', analysis: 'pending' }), 'Syncing GitHub data…'],
    ['analyzing', running({ analysis: 'running' }), 'Analyzing your profile…'],
  ])('shows %s while the sync runs', async (_name, job, text) => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/sync/status': () => json({ job, last_synced_at: COMPLETED_JOB.completed_at }),
    })
    renderRoute('/app')
    expect(await screen.findByText(text)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeDisabled()
  })

  it('shows finding projects while discovery runs', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/discovery/status': () =>
        json({ ...NEVER_DISCOVERED, job: discoveryJob('RUNNING') }),
    })
    renderRoute('/app')
    expect(await screen.findByText('Finding projects…')).toBeInTheDocument()
  })

  it('shows preparing recommendations while a generation runs', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () =>
        json({ ...GENERATED, job: { ...GENERATED.job, status: 'RUNNING' } }),
    })
    renderRoute('/app')
    expect(await screen.findByText('Preparing recommendations…')).toBeInTheDocument()
  })

  it('shows nothing when idle', async () => {
    mockFetch(WITH_RECOMMENDATION)
    renderRoute('/app')
    await screen.findByRole('article', { name: 'httpx' })
    for (const text of ['Syncing GitHub data…', 'Finding projects…', 'Preparing recommendations…'])
      expect(screen.queryByText(text)).not.toBeInTheDocument()
  })
})

describe('your data', () => {
  it('deletes GitHub data only after confirmation, then goes to onboarding', async () => {
    let deleted = false
    const fetchMock = mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/sync/status': () =>
        json(
          deleted
            ? { job: null, last_synced_at: null }
            : { job: COMPLETED_JOB, last_synced_at: COMPLETED_JOB.completed_at },
        ),
      'DELETE /api/v1/profile/github-data': () => {
        deleted = true
        return noContent()
      },
    })
    const { router } = renderRoute('/app')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Delete GitHub data' }))
    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toHaveTextContent(/recommendations, saved and hidden projects/)
    expect(callsTo(fetchMock.mock.calls, 'DELETE', '/api/v1/profile/github-data')).toHaveLength(0)

    await user.click(within(dialog).getByRole('button', { name: 'Delete data' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/onboarding'))
    const [, init] = callsTo(fetchMock.mock.calls, 'DELETE', '/api/v1/profile/github-data')[0]!
    expect(new Headers(init!.headers).get('X-CSRFToken')).toBe('test-csrf-token')
    expect(await screen.findByRole('button', { name: /sync/i })).toBeInTheDocument()
  })

  it('cancelling the account deletion deletes nothing', async () => {
    const fetchMock = mockFetch(WITH_RECOMMENDATION)
    renderRoute('/app')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Delete account' }))
    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toHaveTextContent(/cannot be undone/)
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(callsTo(fetchMock.mock.calls, 'DELETE', '/api/v1/auth/account')).toHaveLength(0)
  })

  it('deletes the account after confirmation and returns to the landing page', async () => {
    let signedIn = true
    const fetchMock = mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/auth/me': () => (signedIn ? json(ME) : unauthenticated()),
      'DELETE /api/v1/auth/account': () => {
        signedIn = false
        return noContent()
      },
    })
    const { router } = renderRoute('/app')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Delete account' }))
    await user.click(
      within(await screen.findByRole('alertdialog')).getByRole('button', {
        name: 'Delete account',
      }),
    )

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    expect(await screen.findByRole('link', { name: /continue with github/i })).toBeInTheDocument()
    expect(callsTo(fetchMock.mock.calls, 'DELETE', '/api/v1/auth/account')).toHaveLength(1)
  })

  it('links to the privacy page', async () => {
    mockFetch(WITH_RECOMMENDATION)
    renderRoute('/app')
    const section = await screen.findByRole('region', { name: 'Your data' })
    expect(within(section).getByRole('link', { name: /what we store/i })).toHaveAttribute(
      'href',
      '/privacy',
    )
  })
})

describe('privacy page', () => {
  it('renders signed out with every data category, retention and how to delete', async () => {
    mockFetch({ 'GET /api/v1/auth/me': () => unauthenticated() })
    renderRoute('/privacy')
    expect(
      await screen.findByRole('heading', { name: 'Your data in ContribFinder' }),
    ).toBeInTheDocument()
    for (const category of [
      'GitHub account identifier and username',
      'Profile README',
      'Public repository metadata and README content',
      'Public contribution information',
      'Derived developer profile',
      'Recommendations',
      'Saved and hidden projects',
      'Feedback events',
      'Audit entries',
    ])
      expect(screen.getByText(category)).toBeInTheDocument()
    expect(screen.getAllByText(/^Kept:/).length).toBeGreaterThanOrEqual(9)
    expect(screen.getByRole('heading', { name: 'How to delete it' })).toBeInTheDocument()
  })

  it('is linked from the landing page', async () => {
    mockFetch({ 'GET /api/v1/auth/me': () => unauthenticated() })
    renderRoute('/')
    expect(await screen.findByRole('link', { name: 'What we store' })).toHaveAttribute(
      'href',
      '/privacy',
    )
  })
})
