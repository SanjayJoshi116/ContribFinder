import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  COMPLETED_JOB,
  ME,
  NEVER_DISCOVERED,
  SYNCED_USER,
  callsTo,
  discoveryJob,
  json,
  mockFetch,
  noContent,
  page,
  renderRoute,
  unauthenticated,
} from '@/test/render'
import { dataVersionsKey } from '@/app/dataVersions'

const ME_ROUTE = { 'GET /api/v1/auth/me': () => json(ME) }

/** Lets the query cache notify its observers (TanStack batches on a timer). */
const settle = () => act(() => new Promise((resolve) => setTimeout(resolve, 50)))

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
  setup: { ci: null, tests: null, dev_environment: null, docker_compose: null },
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

const WITH_RECOMMENDATION = {
  ...ME_ROUTE,
  ...SYNCED_USER,
  'GET /api/v1/recommendations/status': () => json(GENERATED),
  'GET /api/v1/recommendations': () => page([RECOMMENDATION]),
}

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
    expect(callsTo(fetchMock, 'POST', '/api/v1/recommendations/7/save')).toHaveLength(1)
  })

  it('sends one request for a double click on Save', async () => {
    let answer: (response: Response) => void = () => {}
    const fetchMock = mockFetch({
      ...WITH_RECOMMENDATION,
      'POST /api/v1/recommendations/7/save': () =>
        new Promise<Response>((resolve) => {
          answer = resolve
        }),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })

    await userEvent.dblClick(within(card).getByRole('button', { name: 'Save' }))
    // Shown as Saved at once (optimistic), but locked until the request settles.
    expect(within(card).getByRole('button', { name: 'Saved' })).toBeDisabled()
    answer(json({ saved: true }))

    await waitFor(() => expect(within(card).getByRole('button', { name: 'Saved' })).toBeEnabled())
    expect(callsTo(fetchMock, 'POST', '/api/v1/recommendations/7/save')).toHaveLength(1)
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/recommendations/7/save')).toHaveLength(0)
  })

  it('returns to sign-in when Save finds the session ended', async () => {
    let meCalls = 0
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/auth/me': () => (meCalls++ === 0 ? json(ME) : unauthenticated()),
      'POST /api/v1/recommendations/7/save': unauthenticated,
    })
    const { router } = renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })

    await userEvent.click(within(card).getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/your session ended/i)
    expect(router.state.location.pathname).toBe('/')
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

  it('unsaves by repository, so a recommendation regenerated away still unsaves', async () => {
    const fetchMock = mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () => page([{ ...RECOMMENDATION, saved: true }]),
      'DELETE /api/v1/saved/70': () => new Response(null, { status: 204 }),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })

    await userEvent.click(within(card).getByRole('button', { name: 'Saved' }))

    expect(await within(card).findByRole('button', { name: 'Save' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/saved/70')).toHaveLength(1)
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/recommendations/7/save')).toHaveLength(0)
  })

  it('rolls Unsave back when the request fails', async () => {
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () => page([{ ...RECOMMENDATION, saved: true }]),
      'DELETE /api/v1/saved/70': () => json({ error: { code: 'error', message: 'Nope' } }, 500),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })
    await userEvent.click(within(card).getByRole('button', { name: 'Saved' }))
    expect(await within(card).findByRole('button', { name: 'Saved' })).toHaveAttribute(
      'aria-pressed',
      'true',
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
      expect(callsTo(fetchMock, 'POST', '/api/v1/recommendations/7/dismiss')).toHaveLength(1),
    )
    // A plain dismiss is the request it was before reasons: no body.
    expect(callsTo(fetchMock, 'POST', '/api/v1/recommendations/7/dismiss')[0]![1]?.body).toBe(
      undefined,
    )
    answerDismiss()
    const notice = await screen.findByText(/hidden encode\/httpx/i)
    await userEvent.click(within(notice.parentElement!).getByRole('button', { name: 'Undo' }))

    await waitFor(() =>
      expect(callsTo(fetchMock, 'DELETE', '/api/v1/dismissed/70')).toHaveLength(1),
    )
    await waitFor(() => expect(screen.queryByText(/hidden encode\/httpx/i)).not.toBeInTheDocument())
  })

  it('dismisses with a chosen reason, with the same Undo', async () => {
    // The server stops listing a dismissed recommendation; the list is refetched after it.
    let dismissed = false
    const fetchMock = mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () => page(dismissed ? [] : [RECOMMENDATION]),
      'POST /api/v1/recommendations/7/dismiss': () => {
        dismissed = true
        return noContent()
      },
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })

    const toggle = within(card).getByRole('button', { name: 'Dismiss with a reason' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const menu = within(card).getByRole('menu', { name: 'Dismiss with a reason' })
    expect(
      within(menu)
        .getAllByRole('menuitem')
        .map((item) => item.textContent),
    ).toEqual(['Not my stack', 'Too big', 'Inactive', 'Already know it'])
    await userEvent.click(within(menu).getByRole('menuitem', { name: 'Too big' }))

    await waitFor(() =>
      expect(screen.queryByRole('article', { name: 'httpx' })).not.toBeInTheDocument(),
    )
    const [call] = callsTo(fetchMock, 'POST', '/api/v1/recommendations/7/dismiss')
    expect(JSON.parse(String(call![1]?.body))).toEqual({ reason: 'too_big' })
    expect(await screen.findByText(/hidden encode\/httpx/i)).toBeInTheDocument()
  })

  it('works the reason menu from the keyboard', async () => {
    const fetchMock = mockFetch({
      ...WITH_RECOMMENDATION,
      'POST /api/v1/recommendations/7/dismiss': () => noContent(),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })
    const toggle = within(card).getByRole('button', { name: 'Dismiss with a reason' })

    toggle.focus()
    await userEvent.keyboard('{Enter}')
    const items = within(card).getAllByRole('menuitem')
    expect(items[0]).toHaveFocus()
    await userEvent.keyboard('{ArrowDown}')
    expect(items[1]).toHaveFocus()
    await userEvent.keyboard('{ArrowUp}{ArrowUp}')
    expect(items[3]).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    expect(within(card).queryByRole('menu')).not.toBeInTheDocument()
    expect(toggle).toHaveFocus()
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    await userEvent.keyboard('{ArrowDown}')
    expect(within(card).getAllByRole('menuitem')[0]).toHaveFocus()
    await userEvent.click(document.body)
    expect(within(card).queryByRole('menu')).not.toBeInTheDocument()
    expect(callsTo(fetchMock, 'POST', '/api/v1/recommendations/7/dismiss')).toHaveLength(0)
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

  it('moves back a page when the last card on it is dismissed', async () => {
    let dismissed = false
    const other = {
      ...RECOMMENDATION,
      id: 8,
      repository_id: 80,
      repository: { ...REPOSITORY, name: 'starlette', full_name: 'encode/starlette' },
    }
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () =>
        json({
          count: 21,
          next: '/api/v1/recommendations?page=2',
          previous: null,
          results: [other],
        }),
      'GET /api/v1/recommendations?page=2': () =>
        json({
          count: dismissed ? 20 : 21,
          next: null,
          previous: '/api/v1/recommendations',
          results: dismissed ? [] : [RECOMMENDATION],
        }),
      'POST /api/v1/recommendations/7/dismiss': () => {
        dismissed = true
        return noContent()
      },
    })
    const { router } = renderRoute('/app?page=2')
    const card = await screen.findByRole('article', { name: 'httpx' })

    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }))

    expect(await screen.findByRole('article', { name: 'starlette' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('')
    expect(screen.getByText(/hidden encode\/httpx/i)).toBeInTheDocument()
    expect(screen.queryByText(/no recommendations/i)).not.toBeInTheDocument()
  })

  it('stays on the page when dismissing its last card fails', async () => {
    let failDismiss: () => void = () => {}
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations?page=2': () =>
        json({
          count: 21,
          next: null,
          previous: '/api/v1/recommendations',
          results: [RECOMMENDATION],
        }),
      'POST /api/v1/recommendations/7/dismiss': () =>
        new Promise<Response>((resolve) => {
          failDismiss = () =>
            resolve(json({ error: { code: 'server_error', message: 'Down.' } }, 500))
        }),
    })
    const { router } = renderRoute('/app?page=2')
    const card = await screen.findByRole('article', { name: 'httpx' })

    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }))
    await waitFor(() => expect(screen.queryByRole('article', { name: 'httpx' })).toBeNull())
    // The emptied page is only optimistic until the server answers.
    expect(router.state.location.search).toBe('?page=2')

    failDismiss()

    expect(await screen.findByRole('article', { name: 'httpx' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('?page=2')
  })

  it('times Undo from the dismissal, not from a later filter change', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations?language=python': () => page([RECOMMENDATION]),
      'POST /api/v1/recommendations/7/dismiss': () => noContent(),
    })
    renderRoute('/app?language=python')
    const card = await screen.findByRole('article', { name: 'httpx' })

    await user.click(within(card).getByRole('button', { name: 'Dismiss' }))
    expect(await screen.findByText(/hidden encode\/httpx/i)).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(6000)
    await user.selectOptions(screen.getByRole('combobox', { name: 'Language' }), '')
    expect(screen.getByText(/hidden encode\/httpx/i)).toBeInTheDocument()

    // Still open just before 10 s from the dismissal, gone right after (not 6 s later).
    await vi.advanceTimersByTimeAsync(3500)
    expect(screen.getByText(/hidden encode\/httpx/i)).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(600)
    await waitFor(
      () => expect(screen.queryByText(/hidden encode\/httpx/i)).not.toBeInTheDocument(),
      { timeout: 1000 },
    )
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
      expect(callsTo(fetchMock, 'POST', '/api/v1/recommendations/7/feedback')).toHaveLength(1),
    )
    const [, init] = callsTo(fetchMock, 'POST', '/api/v1/recommendations/7/feedback')[0]!
    expect(JSON.parse(init!.body as string)).toEqual({ action: 'viewed' })
    expect(init!.keepalive).toBe(true)
  })

  it('records one view per recommendation when the route moves to another id', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/recommendations/1': () => json({ ...DETAIL, id: 1 }),
      'GET /api/v1/recommendations/2': () =>
        json({
          ...DETAIL,
          id: 2,
          repository: { ...DETAIL.repository, full_name: 'pallets/flask' },
        }),
      'POST /api/v1/recommendations/1/feedback': () => noContent(),
      'POST /api/v1/recommendations/2/feedback': () => noContent(),
    })
    const { router } = renderRoute('/app/recommendations/1')
    await screen.findByRole('heading', { name: 'encode/httpx' })
    await waitFor(() =>
      expect(callsTo(fetchMock, 'POST', '/api/v1/recommendations/1/feedback')).toHaveLength(1),
    )

    await act(() => router.navigate('/app/recommendations/2'))
    await screen.findByRole('heading', { name: 'pallets/flask' })
    await waitFor(() =>
      expect(callsTo(fetchMock, 'POST', '/api/v1/recommendations/2/feedback')).toHaveLength(1),
    )
    expect(callsTo(fetchMock, 'POST', '/api/v1/recommendations/1/feedback')).toHaveLength(1)
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
      const posts = callsTo(fetchMock, 'POST', '/api/v1/recommendations/7/feedback')
      expect(posts).toHaveLength(1)
      expect(JSON.parse(posts[0]![1]!.body as string)).toEqual({ action: 'opened_repository' })
    })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('failed refresh', () => {
  const down = () => json({ error: { code: 'unavailable', message: 'Down.' } }, 503)

  it('keeps the recommendation detail page when its refetch fails', async () => {
    let fail = false
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/recommendations/7': () => (fail ? down() : json(DETAIL)),
      'POST /api/v1/recommendations/7/feedback': () => noContent(),
    })
    const { queryClient } = renderRoute('/app/recommendations/7')
    const title = await screen.findByRole('heading', { level: 1 })

    fail = true
    await act(() => queryClient.refetchQueries({ queryKey: ['profile', 'recommendations'] }))
    await settle()

    expect(queryClient.getQueryState(['profile', 'recommendations', 'detail', 7])?.status).toBe(
      'error',
    )
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(title.textContent!)
    expect(screen.queryByText(/could not load this recommendation/i)).not.toBeInTheDocument()
  })

  it('keeps the saved and hidden lists when their refetch fails', async () => {
    let fail = false
    const saved = {
      repository_id: 70,
      repository: REPOSITORY,
      saved_at: '2026-09-29T10:00:00Z',
      activity_label: '',
      recommendation: null,
    }
    const hidden = {
      repository_id: 72,
      repository: { ...REPOSITORY, full_name: 'meh/thing', name: 'thing' },
      dismissed_at: '2026-09-29T11:00:00Z',
      reason: null,
    }
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/saved?page_size=50': () => (fail ? down() : page([saved])),
      'GET /api/v1/dismissed?page_size=50': () => (fail ? down() : page([hidden])),
    })
    const { queryClient } = renderRoute('/app/saved')
    expect(await screen.findByText('meh/thing')).toBeInTheDocument()

    fail = true
    await act(() =>
      Promise.all([
        queryClient.refetchQueries({ queryKey: ['profile', 'saved'] }),
        queryClient.refetchQueries({ queryKey: ['profile', 'dismissed'] }),
      ]),
    )
    await settle()

    expect(queryClient.getQueryState(['profile', 'saved'])?.status).toBe('error')
    expect(screen.getByText('meh/thing')).toBeInTheDocument()
    expect(screen.getByText(REPOSITORY.full_name)).toBeInTheDocument()
    expect(screen.queryByText(/could not load your/i)).not.toBeInTheDocument()
  })
})

describe('saved projects page', () => {
  it('lists saved projects, marks the ones no longer recommended, and restores hidden ones', async () => {
    let hidden = true
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/saved?page_size=50': () =>
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
      'GET /api/v1/dismissed?page_size=50': () =>
        page(
          hidden
            ? [
                {
                  repository_id: 72,
                  repository: { ...REPOSITORY, full_name: 'meh/thing', name: 'thing' },
                  dismissed_at: '2026-09-29T11:00:00Z',
                  reason: null,
                },
                {
                  repository_id: 73,
                  repository: { ...REPOSITORY, full_name: 'big/monorepo', name: 'monorepo' },
                  dismissed_at: '2026-09-29T09:00:00Z',
                  reason: 'too_big',
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
    const [plain, withReason] = within(hiddenList).getAllByRole('listitem')
    expect(within(withReason!).getByText('Reason: Too big')).toBeInTheDocument()
    expect(within(plain!).queryByText(/reason/i)).not.toBeInTheDocument()
    await userEvent.click(within(plain!).getByRole('button', { name: 'Restore' }))
    expect(await screen.findByText('No hidden projects.')).toBeInTheDocument()
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/dismissed/72')).toHaveLength(1)
  })

  it('shows more saved projects page by page', async () => {
    const saved = (n: number) => ({
      repository_id: 100 + n,
      repository: { ...REPOSITORY, full_name: `org/repo-${n}`, name: `repo-${n}` },
      saved_at: '2026-09-29T10:00:00Z',
      activity_label: '',
      recommendation: null,
    })
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/saved?page_size=50': () =>
        json({
          count: 2,
          next: 'http://testserver/api/v1/saved?cursor=c1&page_size=50',
          previous: null,
          results: [saved(1)],
        }),
      'GET /api/v1/saved?page_size=50&cursor=c1': () =>
        json({ count: 2, next: null, previous: null, results: [saved(2)] }),
      'GET /api/v1/dismissed?page_size=50': () => page([]),
    })
    renderRoute('/app/saved')

    expect(await screen.findByRole('article', { name: 'org/repo-1' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show more' }))

    expect(await screen.findByRole('article', { name: 'org/repo-2' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'org/repo-1' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Show more' })).not.toBeInTheDocument()
  })

  it('continues after the last shown entry when one was unsaved meanwhile', async () => {
    const saved = (n: number) => ({
      repository_id: 100 + n,
      repository: { ...REPOSITORY, full_name: `org/repo-${n}`, name: `repo-${n}` },
      saved_at: '2026-09-29T10:00:00Z',
      activity_label: '',
      recommendation: null,
    })
    // As the server pages: the cursor marks repo-2, so an unsave of repo-1 (in another tab)
    // shifts nothing; a page number would have started the next page at repo-4.
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/saved?page_size=50': () =>
        json({
          count: 4,
          next: 'http://testserver/api/v1/saved?page_size=50&cursor=after-2',
          previous: null,
          results: [saved(1), saved(2)],
        }),
      'GET /api/v1/saved?page_size=50&cursor=after-2': () =>
        json({ count: 3, next: null, previous: null, results: [saved(3), saved(4)] }),
      'GET /api/v1/dismissed?page_size=50': () => page([]),
    })
    renderRoute('/app/saved')

    await userEvent.click(await screen.findByRole('button', { name: 'Show more' }))

    expect(await screen.findByRole('article', { name: 'org/repo-4' })).toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(4)
    for (const n of [1, 2, 3, 4]) {
      expect(screen.getAllByRole('article', { name: `org/repo-${n}` })).toHaveLength(1)
    }
    expect(callsTo(fetchMock, 'GET', '/api/v1/saved?page_size=50&cursor=after-2')).toHaveLength(1)
  })

  it('keeps loaded hidden projects listed after a restore', async () => {
    const hidden = (n: number) => ({
      repository_id: 200 + n,
      repository: { ...REPOSITORY, full_name: `org/hidden-${n}`, name: `hidden-${n}` },
      dismissed_at: '2026-09-29T11:00:00Z',
    })
    let restored = false
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/saved?page_size=50': () => page([]),
      'GET /api/v1/dismissed?page_size=50': () =>
        json({
          count: 3,
          next: 'http://testserver/api/v1/dismissed?cursor=c2&page_size=50',
          previous: null,
          results: [hidden(1), hidden(2)],
        }),
      'GET /api/v1/dismissed?page_size=50&cursor=c2': () =>
        json({
          count: restored ? 2 : 3,
          next: null,
          previous: null,
          results: restored ? [] : [hidden(3)],
        }),
      'DELETE /api/v1/dismissed/203': () => {
        restored = true
        return noContent()
      },
    })
    renderRoute('/app/saved')

    await userEvent.click(await screen.findByRole('button', { name: 'Show more' }))
    const list = screen.getByRole('list', { name: 'Hidden projects' })
    await within(list).findByText('org/hidden-3')
    const last = within(list).getByText('org/hidden-3').closest('li')!
    await userEvent.click(within(last).getByRole('button', { name: 'Restore' }))

    await waitFor(() => expect(within(list).queryByText('org/hidden-3')).not.toBeInTheDocument())
    expect(within(list).getByText('org/hidden-1')).toBeInTheDocument()
    expect(within(list).getByText('org/hidden-2')).toBeInTheDocument()
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

  it('says a stalled sync stopped and lets the user start a new one', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/sync/status': () =>
        json({
          job: { ...running({ repositories: 'running' }), stalled: true },
          last_synced_at: COMPLETED_JOB.completed_at,
        }),
      'POST /api/v1/profile/sync': () => json({ ...running({ profile: 'pending' }), id: 6 }, 202),
    })
    renderRoute('/app')
    expect(await screen.findByText(/Background work stopped/)).toBeInTheDocument()
    expect(screen.queryByText('Syncing GitHub data…')).not.toBeInTheDocument()
    const refresh = screen.getByRole('button', { name: 'Refresh' })
    expect(refresh).toBeEnabled()
    await userEvent.setup().click(refresh)
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/profile/sync')).toHaveLength(1))
  })

  it('says a stalled discovery stopped instead of finding projects', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/discovery/status': () =>
        json({ ...NEVER_DISCOVERED, job: { ...discoveryJob('RUNNING'), stalled: true } }),
    })
    renderRoute('/app')
    // The header and the discovery card both say so (PIPE-5).
    const card = await screen.findByRole('region', { name: 'Project discovery' })
    expect(await within(card).findByText(/Background work stopped/)).toBeInTheDocument()
    expect(screen.getAllByText(/Background work stopped/)).toHaveLength(2)
    expect(screen.queryByText(/finding projects/i)).not.toBeInTheDocument()
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
    const { router, queryClient } = renderRoute('/app')
    const reset = vi.spyOn(queryClient, 'resetQueries')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Delete GitHub data' }))
    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toHaveTextContent(/recommendations, saved and hidden projects/)
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/profile/github-data')).toHaveLength(0)

    await user.click(within(dialog).getByRole('button', { name: 'Delete data' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/onboarding'))
    const [, init] = callsTo(fetchMock, 'DELETE', '/api/v1/profile/github-data')[0]!
    expect(new Headers(init!.headers).get('X-CSRFToken')).toBe('test-csrf-token')
    expect(await screen.findByRole('button', { name: /sync/i })).toBeInTheDocument()
    // The next data versions fetch is a first one again, so it refetches nothing.
    expect(reset).toHaveBeenCalledWith({ queryKey: dataVersionsKey })
  })

  it('cancelling the account deletion deletes nothing', async () => {
    const fetchMock = mockFetch(WITH_RECOMMENDATION)
    renderRoute('/app')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Delete account' }))
    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toHaveTextContent(/cannot be undone/)
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/auth/account')).toHaveLength(0)
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
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/auth/account')).toHaveLength(1)
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
      'GitHub account ID',
      'GitHub username, avatar and display name',
      'Profile README',
      'Public repository metadata and README content',
      'Public contribution information',
      'Derived developer profile',
      'Candidate projects and search queries',
      'Recommendations',
      'Saved and hidden projects',
      'Feedback events',
      'Sync and job history',
      'Sign-in sessions',
      'Audit entries',
    ])
      expect(screen.getByText(category)).toBeInTheDocument()
    expect(screen.getAllByText(/^Kept:/).length).toBeGreaterThanOrEqual(14)
    expect(screen.getByText('Kept: Until you delete your account.')).toBeInTheDocument()
    expect(screen.getByText(/address hash are removed/)).toBeInTheDocument()
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

// --- feedback-ui-review-fixes (FBK-1…FBK-5) --------------------------------------------------

const FAIL = () => json({ error: { code: 'server_error', message: 'Down.' } }, 500)

/** A response the test answers later. */
function later() {
  let answer: (response: Response) => void = () => {}
  const response = new Promise<Response>((resolve) => {
    answer = resolve
  })
  return { response, answer: (r: Response) => act(async () => answer(r)) }
}

const OTHER = {
  ...RECOMMENDATION,
  id: 8,
  repository_id: 80,
  repository: { ...REPOSITORY, name: 'starlette', full_name: 'encode/starlette' },
}

const cardNames = () =>
  screen.getAllByRole('article').map((article) => within(article).getByRole('heading').textContent)

describe('failed feedback actions', () => {
  it("a failed save does not bring back another card's confirmed dismissal", async () => {
    const save = later()
    let dismissed = false
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () =>
        page(dismissed ? [RECOMMENDATION] : [RECOMMENDATION, OTHER]),
      'POST /api/v1/recommendations/7/save': () => save.response,
      'POST /api/v1/recommendations/8/dismiss': () => {
        dismissed = true
        return noContent()
      },
    })
    renderRoute('/app')
    const a = await screen.findByRole('article', { name: 'httpx' })
    const b = screen.getByRole('article', { name: 'starlette' })

    await userEvent.click(within(a).getByRole('button', { name: 'Save' }))
    await userEvent.click(within(b).getByRole('button', { name: 'Dismiss' }))
    expect(await screen.findByText(/hidden encode\/starlette/i)).toBeInTheDocument()
    await save.answer(FAIL())

    const card = await screen.findByRole('article', { name: 'httpx' })
    expect(await within(card).findByText("Couldn't save.")).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: 'Save' })).toBeEnabled()
    expect(screen.queryByRole('article', { name: 'starlette' })).not.toBeInTheDocument()
  })

  it('puts a card whose dismissal failed back at its place, with an error', async () => {
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () => page([RECOMMENDATION, OTHER]),
      'POST /api/v1/recommendations/7/dismiss': FAIL,
    })
    renderRoute('/app')
    const a = await screen.findByRole('article', { name: 'httpx' })

    await userEvent.click(within(a).getByRole('button', { name: 'Dismiss' }))

    const back = await screen.findByRole('article', { name: 'httpx' })
    expect(await within(back).findByText("Couldn't hide.")).toBeInTheDocument()
    expect(cardNames()).toEqual(['httpx', 'starlette'])
    expect(within(back).getByRole('button', { name: 'Dismiss' })).toBeEnabled()
  })

  it("a failed save does not undo another card's unsave", async () => {
    const save = later()
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () => page([RECOMMENDATION, { ...OTHER, saved: true }]),
      'POST /api/v1/recommendations/7/save': () => save.response,
      'DELETE /api/v1/saved/80': () => noContent(),
    })
    renderRoute('/app')
    const a = await screen.findByRole('article', { name: 'httpx' })
    const c = screen.getByRole('article', { name: 'starlette' })

    await userEvent.click(within(a).getByRole('button', { name: 'Save' }))
    await userEvent.click(within(c).getByRole('button', { name: 'Saved' }))
    await waitFor(() => expect(within(c).getByRole('button', { name: 'Save' })).toBeEnabled())
    await save.answer(FAIL())

    expect(await within(a).findByText("Couldn't save.")).toBeInTheDocument()
    expect(within(c).getByRole('button', { name: 'Save' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('clears the save error when a retry succeeds', async () => {
    let calls = 0
    mockFetch({
      ...WITH_RECOMMENDATION,
      'POST /api/v1/recommendations/7/save': () => (calls++ === 0 ? FAIL() : json({ saved: true })),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })
    await userEvent.click(within(card).getByRole('button', { name: 'Save' }))
    expect(await within(card).findByText("Couldn't save.")).toBeInTheDocument()

    await userEvent.click(within(card).getByRole('button', { name: 'Save' }))

    expect(await within(card).findByRole('button', { name: 'Saved' })).toBeEnabled()
    expect(within(card).queryByText("Couldn't save.")).not.toBeInTheDocument()
  })

  it('says when unsaving from a card fails', async () => {
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () => page([{ ...RECOMMENDATION, saved: true }]),
      'DELETE /api/v1/saved/70': FAIL,
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })
    await userEvent.click(within(card).getByRole('button', { name: 'Saved' }))
    expect(await within(card).findByText("Couldn't remove.")).toBeInTheDocument()
    expect(within(card).getByRole('button', { name: 'Saved' })).toBeEnabled()
  })

  it('clears the dismiss error when a retry succeeds', async () => {
    let calls = 0
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () => page(calls > 1 ? [] : [RECOMMENDATION]),
      'POST /api/v1/recommendations/7/dismiss': () => (calls++ === 0 ? FAIL() : noContent()),
    })
    renderRoute('/app')
    let card = await screen.findByRole('article', { name: 'httpx' })
    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }))
    card = await screen.findByRole('article', { name: 'httpx' })
    expect(await within(card).findByText("Couldn't hide.")).toBeInTheDocument()

    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }))

    expect(await screen.findByText(/hidden encode\/httpx/i)).toBeInTheDocument()
    expect(screen.queryByText("Couldn't hide.")).not.toBeInTheDocument()
  })

  it('keeps a failed dismissal on the page where it failed', async () => {
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations/7': () => json(DETAIL),
      'POST /api/v1/recommendations/7/feedback': () => noContent(),
      'POST /api/v1/recommendations/7/dismiss': FAIL,
    })
    const { router } = renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })
    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }))
    const back = await screen.findByRole('article', { name: 'httpx' })
    expect(await within(back).findByText("Couldn't hide.")).toBeInTheDocument()

    await act(() => router.navigate('/app/recommendations/7'))
    expect(await screen.findByRole('button', { name: 'Dismiss' })).toBeEnabled()
    expect(screen.queryByText("Couldn't hide.")).not.toBeInTheDocument()

    await act(() => router.navigate(-1))
    expect(await screen.findByRole('article', { name: 'httpx' })).toBeInTheDocument()
    expect(screen.queryByText("Couldn't hide.")).not.toBeInTheDocument()
  })

  it('does not put a failed dismissal back on a page it moved away from', async () => {
    const dismiss = later()
    let lists = 0
    mockFetch({
      ...WITH_RECOMMENDATION,
      // Later refetches never answer: the cache holds what the rollback wrote.
      'GET /api/v1/recommendations': () =>
        lists++ === 0 ? page([RECOMMENDATION, OTHER]) : new Promise<Response>(() => {}),
      'POST /api/v1/recommendations/7/dismiss': () => dismiss.response,
    })
    const { queryClient } = renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })
    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }))
    await waitFor(() => expect(screen.queryByRole('article', { name: 'httpx' })).toBeNull())
    // A refetch meanwhile moved it to page 2 of the same list.
    queryClient.setQueryData(['profile', 'recommendations', 'list', '/recommendations?page=2'], {
      count: 2,
      next: null,
      previous: '/api/v1/recommendations',
      results: [RECOMMENDATION],
    })

    await dismiss.answer(FAIL())
    await settle()

    const first = queryClient.getQueryData<{ results: { id: number }[]; count: number }>([
      'profile',
      'recommendations',
      'list',
      '/recommendations',
    ])
    expect(first?.results.map((r) => r.id)).toEqual([8])
  })

  it('says when dismissing from the detail page fails and stays there', async () => {
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations/7': () => json(DETAIL),
      'POST /api/v1/recommendations/7/feedback': () => noContent(),
      'POST /api/v1/recommendations/7/dismiss': FAIL,
    })
    const { router } = renderRoute('/app/recommendations/7')
    await userEvent.click(await screen.findByRole('button', { name: 'Dismiss' }))
    expect(await screen.findByText("Couldn't hide.")).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/app/recommendations/7')
    expect(screen.getByRole('button', { name: 'Dismiss' })).toBeEnabled()
  })

  const SAVED_ENTRY = {
    repository_id: 70,
    repository: REPOSITORY,
    saved_at: '2026-09-29T10:00:00Z',
    activity_label: '',
    recommendation: null,
  }
  const HIDDEN_ENTRY = {
    repository_id: 72,
    repository: { ...REPOSITORY, full_name: 'meh/thing', name: 'thing' },
    dismissed_at: '2026-09-29T11:00:00Z',
    reason: null,
  }

  it('says when Remove fails on the saved page, and a retry clears it', async () => {
    let calls = 0
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/saved?page_size=50': () => page([SAVED_ENTRY]),
      'GET /api/v1/dismissed?page_size=50': () => page([]),
      'DELETE /api/v1/saved/70': () => (calls++ === 0 ? FAIL() : noContent()),
    })
    renderRoute('/app/saved')
    const entry = await screen.findByRole('article', { name: 'encode/httpx' })
    await userEvent.click(within(entry).getByRole('button', { name: 'Remove' }))
    expect(await within(entry).findByText("Couldn't remove.")).toBeInTheDocument()
    expect(within(entry).getByRole('button', { name: 'Remove' })).toBeEnabled()

    await userEvent.click(within(entry).getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(calls).toBe(2))
    await waitFor(() =>
      expect(within(entry).queryByText("Couldn't remove.")).not.toBeInTheDocument(),
    )
  })

  it('says when Restore fails on the saved page, and a retry clears it', async () => {
    let calls = 0
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/saved?page_size=50': () => page([]),
      'GET /api/v1/dismissed?page_size=50': () => page(calls > 1 ? [] : [HIDDEN_ENTRY]),
      'DELETE /api/v1/dismissed/72': () => (calls++ === 0 ? FAIL() : noContent()),
    })
    renderRoute('/app/saved')
    const list = await screen.findByRole('list', { name: 'Hidden projects' })
    const item = within(list).getByRole('listitem')
    await userEvent.click(within(item).getByRole('button', { name: 'Restore' }))
    expect(await within(item).findByText("Couldn't restore.")).toBeInTheDocument()
    expect(within(item).getByRole('button', { name: 'Restore' })).toBeEnabled()

    await userEvent.click(within(item).getByRole('button', { name: 'Restore' }))
    expect(await screen.findByText('No hidden projects.')).toBeInTheDocument()
  })

  it('says when "Show more" fails, keeps the entries and lets it be tried again', async () => {
    let calls = 0
    const more = {
      ...HIDDEN_ENTRY,
      repository_id: 73,
      repository: { ...REPOSITORY, full_name: 'big/monorepo', name: 'monorepo' },
    }
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/saved?page_size=50': () => page([]),
      'GET /api/v1/dismissed?page_size=50': () =>
        json({
          count: 2,
          next: 'http://testserver/api/v1/dismissed?cursor=c1&page_size=50',
          previous: null,
          results: [HIDDEN_ENTRY],
        }),
      'GET /api/v1/dismissed?page_size=50&cursor=c1': () =>
        calls++ === 0
          ? json({ error: { code: 'bad_request', message: 'No.' } }, 400)
          : json({ count: 2, next: null, previous: null, results: [more] }),
    })
    renderRoute('/app/saved')
    await screen.findByText('meh/thing')
    await userEvent.click(screen.getByRole('button', { name: 'Show more' }))

    expect(await screen.findByText("Couldn't load more.")).toBeInTheDocument()
    expect(screen.getByText('meh/thing')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show more' }))

    expect(await screen.findByText('big/monorepo')).toBeInTheDocument()
    expect(screen.queryByText("Couldn't load more.")).not.toBeInTheDocument()
  })
})

describe('undo notice lifecycle', () => {
  it('gives a second dismissal a fresh notice after a failed undo', async () => {
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations': () => page([RECOMMENDATION, OTHER]),
      'POST /api/v1/recommendations/7/dismiss': () => noContent(),
      'POST /api/v1/recommendations/8/dismiss': () => noContent(),
      'DELETE /api/v1/dismissed/70': FAIL,
    })
    renderRoute('/app')
    const a = await screen.findByRole('article', { name: 'httpx' })
    await userEvent.click(within(a).getByRole('button', { name: 'Dismiss' }))
    const first = await screen.findByText(/hidden encode\/httpx/i)
    await userEvent.click(within(first.parentElement!).getByRole('button', { name: 'Undo' }))
    expect(await screen.findByText("Undo didn't work.")).toBeInTheDocument()

    const b = await screen.findByRole('article', { name: 'starlette' })
    await userEvent.click(within(b).getByRole('button', { name: 'Dismiss' }))

    const second = await screen.findByText(/hidden encode\/starlette/i)
    expect(screen.queryByText("Undo didn't work.")).not.toBeInTheDocument()
    expect(within(second.parentElement!).getByRole('button', { name: 'Undo' })).toBeEnabled()
  })

  async function undoAtNineSeconds(result: () => Response) {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const restore = later()
    mockFetch({
      ...WITH_RECOMMENDATION,
      'POST /api/v1/recommendations/7/dismiss': () => noContent(),
      'DELETE /api/v1/dismissed/70': () => restore.response,
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })
    await user.click(within(card).getByRole('button', { name: 'Dismiss' }))
    const notice = await screen.findByText(/hidden encode\/httpx/i)
    await vi.advanceTimersByTimeAsync(9000)
    await user.click(within(notice.parentElement!).getByRole('button', { name: 'Undo' }))
    await vi.advanceTimersByTimeAsync(3000)
    // Past 10 s from the dismissal, still open: the undo has not answered yet.
    expect(screen.getByText(/hidden encode\/httpx/i)).toBeInTheDocument()
    await restore.answer(result())
  }

  it('keeps a slow failed undo visible for 10 s from the failure', async () => {
    await undoAtNineSeconds(FAIL)
    expect(await screen.findByText("Undo didn't work.")).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(9500)
    expect(screen.getByText(/hidden encode\/httpx/i)).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(1000)
    await waitFor(() => expect(screen.queryByText(/hidden encode\/httpx/i)).not.toBeInTheDocument())
  })

  it('closes the notice when a slow undo succeeds', async () => {
    await undoAtNineSeconds(noContent)
    await waitFor(() => expect(screen.queryByText(/hidden encode\/httpx/i)).not.toBeInTheDocument())
  })

  it('stays where the user went when a detail-page dismissal is confirmed later', async () => {
    const dismiss = later()
    mockFetch({
      ...WITH_RECOMMENDATION,
      'GET /api/v1/recommendations/7': () => json(DETAIL),
      'POST /api/v1/recommendations/7/feedback': () => noContent(),
      'POST /api/v1/recommendations/7/dismiss': () => dismiss.response,
      'GET /api/v1/saved?page_size=50': () => page([]),
      'GET /api/v1/dismissed?page_size=50': () => page([]),
    })
    const { router } = renderRoute('/app/recommendations/7')
    await userEvent.click(await screen.findByRole('button', { name: 'Dismiss' }))
    await act(() => router.navigate('/app/saved'))
    await dismiss.answer(noContent())
    await settle()

    expect(router.state.location.pathname).toBe('/app/saved')
  })
})
