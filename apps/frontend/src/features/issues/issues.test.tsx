import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ME, json, mockFetch, noContent, renderRoute } from '@/test/render'

const ME_ROUTE = { 'GET /api/v1/auth/me': () => json(ME) }

/** Lets the query cache notify its observers (TanStack batches on a timer). */
const settle = () => act(() => new Promise((resolve) => setTimeout(resolve, 50)))

const ISSUE = {
  id: 31,
  github: {
    repository_full_name: 'encode/httpx',
    number: 12,
    title: 'Fix typo in the Django guide',
    body: '<img src=x onerror="alert(1)"> Steps:\n1. Open the **guide**',
    labels: ['good first issue', 'kind/docs'],
    state: 'open',
    comments: 2,
    created_at: '2026-09-20T10:00:00Z',
    updated_at: '2026-09-28T10:00:00Z',
    url: 'https://github.com/encode/httpx/issues/12',
  },
  analysis: {
    labels: ['good_first_issue', 'documentation'],
    contribution_type: 'documentation',
    contribution_type_evidence: { by: 'label', value: 'documentation', taxonomy: '2026.10.1' },
    difficulty: 'beginner',
    difficulty_evidence: {
      signals: [
        { signal: 'label', vote: 'beginner', value: 'good first issue' },
        { signal: 'body_length', vote: 'beginner', value: 58 },
        { signal: 'technology_count', vote: 'beginner', value: 1 },
        { signal: 'contribution_type', vote: 'beginner', value: 'documentation' },
        { signal: 'comments', vote: null, value: 2 },
      ],
      votes: { beginner: 4, intermediate: 0, advanced: 0 },
    },
    technologies: [
      { slug: 'django', name: 'Django', source: 'title', matched: true },
      { slug: 'react', name: 'React', source: 'body', matched: false },
    ],
    reasons: [
      { type: 'technology', text: 'Mentions Django, which you use', detail: {} },
      { type: 'difficulty', text: 'Estimated beginner-level: a good fit', detail: {} },
      { type: 'approachability', text: 'Labeled "good first issue"', detail: {} },
    ],
    recommendation: { id: 7, repository_full_name: 'encode/httpx', match_label: 'strong' },
  },
}

const UNKNOWN = {
  ...ISSUE,
  analysis: {
    ...ISSUE.analysis,
    contribution_type: 'unknown',
    contribution_type_evidence: {},
    difficulty: 'unknown',
    difficulty_evidence: {
      signals: [{ signal: 'label', vote: 'beginner', value: 'good first issue' }],
      votes: { beginner: 1, intermediate: 0, advanced: 0 },
    },
  },
}

beforeEach(() => {
  document.cookie = 'csrftoken=test-csrf-token'
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('issue detail page', () => {
  it('separates GitHub data from ContribFinder analysis', async () => {
    mockFetch({ ...ME_ROUTE, 'GET /api/v1/issues/31': () => json(ISSUE) })
    renderRoute('/app/issues/31')

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
      'Fix typo in the Django guide',
    )
    expect(screen.getByText('encode/httpx #12')).toBeInTheDocument()

    const github = screen.getByRole('region', { name: 'From GitHub' })
    const labels = within(github).getByRole('list', { name: 'Labels' })
    expect(within(labels).getByText('kind/docs')).toBeInTheDocument()
    expect(within(github).getByText('Open')).toBeInTheDocument()

    const analysis = screen.getByRole('region', { name: 'ContribFinder analysis' })
    expect(within(analysis).getByText('Documentation')).toBeInTheDocument()
    expect(within(analysis).getByText('From a documentation label')).toBeInTheDocument()
    expect(within(analysis).getByText('Beginner (estimated)')).toBeInTheDocument()
    expect(
      within(analysis).getByText(
        'Based on: Label "good first issue", Short description, Mentions one technology, Documentation work',
      ),
    ).toBeInTheDocument()
    expect(within(analysis).getByText('Mentions Django, which you use')).toBeInTheDocument()
    const technologies = within(analysis).getByRole('list', { name: 'Technologies' })
    expect(within(technologies).getByText(/in your profile/)).toBeInTheDocument()
    expect(within(github).queryByText('Mentions Django, which you use')).not.toBeInTheDocument()

    expect(screen.getByRole('link', { name: '← Back to encode/httpx' })).toHaveAttribute(
      'href',
      '/app/recommendations/7',
    )
    expect(document.body.textContent).not.toMatch(/%/)
  })

  it('shows the description as plain text, never as HTML', async () => {
    mockFetch({ ...ME_ROUTE, 'GET /api/v1/issues/31': () => json(ISSUE) })
    renderRoute('/app/issues/31')

    const body = await screen.findByTestId('issue-body')
    expect(body.textContent).toBe(ISSUE.github.body)
    expect(body.querySelector('img')).toBeNull()
    expect(body.querySelector('strong')).toBeNull()
    expect(document.querySelector('img[src="x"]')).toBeNull()
  })

  it('shows unknown analysis as not enough evidence', async () => {
    mockFetch({ ...ME_ROUTE, 'GET /api/v1/issues/31': () => json(UNKNOWN) })
    renderRoute('/app/issues/31')

    const analysis = await screen.findByRole('region', { name: 'ContribFinder analysis' })
    expect(within(analysis).getAllByText('Not enough evidence')).toHaveLength(2)
    expect(within(analysis).queryByText(/Based on/)).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('records opened_issue with the issue id when the GitHub link is followed', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/issues/31': () => json(ISSUE),
      'POST /api/v1/recommendations/7/feedback': () => noContent(),
    })
    renderRoute('/app/issues/31')

    const link = await screen.findByRole('link', { name: 'Open on GitHub' })
    expect(link).toHaveAttribute('href', 'https://github.com/encode/httpx/issues/12')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    await userEvent.click(link)

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([url]) => url === '/api/v1/recommendations/7/feedback'),
      ).toHaveLength(1),
    )
    const [, init] = fetchMock.mock.calls.find(
      ([url]) => url === '/api/v1/recommendations/7/feedback',
    )!
    expect(JSON.parse(String(init!.body))).toEqual({ action: 'opened_issue', issue_id: 31 })
    expect(init!.keepalive).toBe(true)
  })

  it('says when an issue mentions no technology', async () => {
    const plain = { ...ISSUE, analysis: { ...ISSUE.analysis, technologies: [] } }
    mockFetch({ ...ME_ROUTE, 'GET /api/v1/issues/31': () => json(plain) })
    renderRoute('/app/issues/31')

    const analysis = await screen.findByRole('region', { name: 'ContribFinder analysis' })
    expect(within(analysis).getByText('No technologies mentioned')).toBeInTheDocument()
  })

  it('records opened_issue for a middle click on the GitHub link', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/issues/31': () => json(ISSUE),
      'POST /api/v1/recommendations/7/feedback': () => noContent(),
    })
    renderRoute('/app/issues/31')

    const link = await screen.findByRole('link', { name: 'Open on GitHub' })
    fireEvent(link, new MouseEvent('auxclick', { bubbles: true, button: 1 }))

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([url]) => url === '/api/v1/recommendations/7/feedback'),
      ).toHaveLength(1),
    )
  })

  it('keeps the issue shown when a refetch fails', async () => {
    let fail = false
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/issues/31': () =>
        fail ? json({ error: { code: 'unavailable', message: 'Down.' } }, 503) : json(ISSUE),
    })
    const { queryClient } = renderRoute('/app/issues/31')
    expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument()

    fail = true
    await act(() => queryClient.refetchQueries({ queryKey: ['profile', 'issues', 31] }))
    await settle()

    expect(queryClient.getQueryState(['profile', 'issues', 31])?.status).toBe('error')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(ISSUE.github.title)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('ends the page when a refetch says the issue is gone', async () => {
    let gone = false
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/issues/31': () =>
        gone ? json({ error: { code: 'not_found', message: 'Not found.' } }, 404) : json(ISSUE),
    })
    const { queryClient } = renderRoute('/app/issues/31')
    expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument()

    gone = true
    await act(() => queryClient.refetchQueries({ queryKey: ['profile', 'issues', 31] }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /no longer among your relevant issues/,
    )
  })

  it('explains an issue that is no longer relevant', async () => {
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/issues/31': () =>
        json({ error: { code: 'not_found', message: 'Not found.' } }, 404),
    })
    renderRoute('/app/issues/31')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /no longer among your relevant issues/,
    )
    expect(screen.getByRole('link', { name: 'Back to your dashboard' })).toHaveAttribute(
      'href',
      '/app',
    )
  })
})
