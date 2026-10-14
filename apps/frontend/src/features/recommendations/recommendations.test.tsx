import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ME, NEVER_GENERATED, SYNCED_USER, json, mockFetch, renderRoute } from '@/test/render'

import { recommendationStatusKey, recommendationsPath } from './api'

const ME_ROUTE = { 'GET /api/v1/auth/me': () => json(ME) }

const REPOSITORY = {
  full_name: 'encode/httpx',
  owner: 'encode',
  name: 'httpx',
  description: 'A next generation HTTP client for Python.',
  html_url: 'https://github.com/encode/httpx',
  primary_language: 'Python',
  stars: 13000,
  topics: ['python', 'http'],
  license: 'BSD-3-Clause',
}

const OPENNESS = {
  contributing: true,
  code_of_conduct: true,
  issue_templates: false,
  pull_request_template: null,
  good_first_issue: true,
  help_wanted: false,
}

const RECOMMENDATION = {
  id: 7,
  repository: REPOSITORY,
  match_label: 'strong',
  technologies: [
    { slug: 'python', name: 'Python', category: 'language', matched: true },
    { slug: 'trio', name: 'Trio', category: 'library', matched: false },
  ],
  reasons: [
    { type: 'skill', text: 'Shares Python with your profile', detail: {} },
    {
      type: 'language',
      text: 'Written mainly in Python, one of your strongest languages',
      detail: {},
    },
    { type: 'activity', text: 'Recently active: last push 2 days ago', detail: {} },
    { type: 'openness', text: 'Has a contributing guide', detail: {} },
  ],
  activity_label: 'recently_active',
  size: 'large',
  openness: OPENNESS,
  relevant_issue_count: 0,
  generated_at: '2026-09-29T10:00:00Z',
}

const DETAIL = {
  ...RECOMMENDATION,
  languages: [
    { language: 'Python', share: 0.95 },
    { language: 'Shell', share: 0.05 },
  ],
  issues: [],
  readme_excerpt: 'HTTPX is a fully featured HTTP client for Python.',
  activity_signals: {
    captured_at: '2026-09-29T09:00:00Z',
    days_since_push: 2,
    commits_90d: 80,
    prs_merged_90d: 30,
    contributors: 200,
    latest_release_at: '2026-09-01T00:00:00Z',
    open_issues: 45,
  },
}

const page = (results: unknown[], extra: Record<string, unknown> = {}) =>
  json({ count: results.length, next: null, previous: null, results, ...extra })

const GENERATED = {
  job: { id: 9, job_type: 'recommendation_generation', status: 'COMPLETED', steps: {} },
  last_generated_at: '2026-09-29T10:00:00Z',
  count: 1,
  config_version: 'v1-deterministic',
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('recommendationsPath', () => {
  it('orders filters, skips empty ones and page 1', () => {
    expect(recommendationsPath({})).toBe('/recommendations')
    expect(recommendationsPath({ match: 'strong', language: 'c++', page: 1 })).toBe(
      '/recommendations?language=c%2B%2B&match=strong',
    )
    expect(recommendationsPath({ framework: 'django', page: 3 })).toBe(
      '/recommendations?framework=django&page=3',
    )
  })
})

describe('recommendation cards', () => {
  it('show label, reasons, technologies, activity and a GitHub link, never a percentage', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () => json(GENERATED),
      'GET /api/v1/recommendations': () => page([RECOMMENDATION]),
    })
    renderRoute('/app')

    const card = await screen.findByRole('article', { name: 'httpx' })
    expect(within(card).getByText('Strong match')).toBeInTheDocument()
    expect(within(card).getByText('Shares Python with your profile')).toBeInTheDocument()
    expect(within(card).queryByText('Has a contributing guide')).not.toBeInTheDocument() // top 3
    expect(within(card).getByText('Recently active')).toBeInTheDocument()
    const technologies = within(card).getByRole('list', { name: 'Technologies' })
    expect(within(technologies).getByText(/in your profile/)).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: 'Open on GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/encode/httpx',
    )
    const section = screen.getByRole('region', { name: 'Recommended projects' })
    expect(section.textContent).not.toMatch(/%/)
  })

  it('shows the number of relevant issues', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () => json(GENERATED),
      'GET /api/v1/recommendations': () =>
        page([
          RECOMMENDATION,
          {
            ...RECOMMENDATION,
            id: 8,
            repository: { ...REPOSITORY, name: 'one' },
            relevant_issue_count: 1,
          },
          {
            ...RECOMMENDATION,
            id: 9,
            repository: { ...REPOSITORY, name: 'many' },
            relevant_issue_count: 3,
          },
        ]),
    })
    renderRoute('/app')

    const none = await screen.findByRole('article', { name: 'httpx' })
    expect(within(none).queryByText(/relevant issue/)).not.toBeInTheDocument()
    const one = screen.getByRole('article', { name: 'one' })
    expect(within(one).getByRole('link', { name: '1 relevant issue' })).toHaveAttribute(
      'href',
      '/app/recommendations/8#relevant-issues',
    )
    const many = screen.getByRole('article', { name: 'many' })
    expect(within(many).getByText('3 relevant issues')).toBeInTheDocument()
  })

  it('filters by issue difficulty and contribution type through the URL', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () => json({ ...GENERATED, count: 25 }),
      'GET /api/v1/recommendations': () => page([RECOMMENDATION]),
      'GET /api/v1/recommendations?difficulty=beginner': () => page([RECOMMENDATION]),
      'GET /api/v1/recommendations?difficulty=beginner&contribution_type=documentation': () =>
        page([]),
    })
    const { router } = renderRoute('/app')
    await screen.findByRole('article', { name: 'httpx' })

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Issue difficulty' }),
      'beginner',
    )
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Contribution type' }),
      'documentation',
    )

    expect(await screen.findByText('No recommendations match these filters.')).toBeInTheDocument()
    expect(router.state.location.search).toBe(
      '?difficulty=beginner&contribution_type=documentation',
    )
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).endsWith('?difficulty=beginner&contribution_type=documentation'),
      ),
    ).toBe(true)
  })

  it('hides filters when everything fits on one page', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () => json({ ...GENERATED, count: 10 }),
      'GET /api/v1/recommendations': () => page([RECOMMENDATION]),
    })
    renderRoute('/app')
    await screen.findByRole('article', { name: 'httpx' })
    expect(screen.queryByRole('form', { name: 'Filter recommendations' })).not.toBeInTheDocument()
  })

  it('filters through the URL', async () => {
    const fetchMock = mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () => json({ ...GENERATED, count: 25 }),
      'GET /api/v1/recommendations': () => page([RECOMMENDATION]),
      'GET /api/v1/recommendations?language=python': () => page([]),
    })
    const { router } = renderRoute('/app')
    await screen.findByRole('article', { name: 'httpx' })

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Language' }), 'python')

    expect(await screen.findByText('No recommendations match these filters.')).toBeInTheDocument()
    expect(router.state.location.search).toBe('?language=python')
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('?language=python'))).toBe(
      true,
    )
  })

  it('keeps filters from the URL on load', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () => json(GENERATED),
      'GET /api/v1/recommendations?activity=recently_active&match=strong': () =>
        page([RECOMMENDATION]),
    })
    renderRoute('/app?match=strong&activity=recently_active')
    expect(await screen.findByRole('article', { name: 'httpx' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Match' })).toHaveValue('strong')
  })

  it('shows generating, then the list without a reload', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let statusCalls = 0
    let listCalls = 0
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () => {
        statusCalls += 1
        return statusCalls === 1
          ? json({ ...NEVER_GENERATED, job: { ...GENERATED.job, status: 'RUNNING' } })
          : json(GENERATED)
      },
      'GET /api/v1/recommendations': () => {
        listCalls += 1
        return listCalls === 1 ? page([]) : page([RECOMMENDATION])
      },
    })
    renderRoute('/app')

    expect(await screen.findByText('Preparing your recommendations…')).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(3100)
    expect(await screen.findByRole('article', { name: 'httpx' })).toBeInTheDocument()
    expect(screen.queryByText('Preparing your recommendations…')).not.toBeInTheDocument()
  })

  it('shows the list when a generation finishes between two polls', async () => {
    let statusCalls = 0
    let listCalls = 0
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () => {
        statusCalls += 1
        return statusCalls === 1 ? json(NEVER_GENERATED) : json(GENERATED)
      },
      'GET /api/v1/recommendations': () => {
        listCalls += 1
        return listCalls === 1 ? page([]) : page([RECOMMENDATION])
      },
    })
    const { queryClient } = renderRoute('/app')

    expect(
      await screen.findByText('Recommendations appear here once project discovery has finished.'),
    ).toBeInTheDocument()
    // What the pipeline does when discovery ends; the generation has already completed.
    await queryClient.invalidateQueries({ queryKey: recommendationStatusKey })
    expect(await screen.findByRole('article', { name: 'httpx' })).toBeInTheDocument()
  })

  it('explains an empty list before the first generation', async () => {
    mockFetch({ ...ME_ROUTE, ...SYNCED_USER })
    renderRoute('/app')
    expect(
      await screen.findByText('Recommendations appear here once project discovery has finished.'),
    ).toBeInTheDocument()
  })
})

describe('recommendation detail page', () => {
  it('separates GitHub facts from ContribFinder analysis', async () => {
    mockFetch({ ...ME_ROUTE, 'GET /api/v1/recommendations/7': () => json(DETAIL) })
    renderRoute('/app/recommendations/7')

    const analysis = await screen.findByRole('region', { name: 'ContribFinder analysis' })
    expect(within(analysis).getByText('Has a contributing guide')).toBeInTheDocument()
    expect(within(analysis).getByText(/Recently active · Large project/)).toBeInTheDocument()
    const github = screen.getByRole('region', { name: 'From GitHub' })
    expect(
      within(github).getByText('HTTPX is a fully featured HTTP client for Python.'),
    ).toBeVisible()
    expect(within(github).getByText('200 contributors')).toBeInTheDocument()
    expect(within(github).getByText('BSD-3-Clause')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('encode/httpx')
    expect(document.body.textContent).not.toMatch(/%/)
  })

  it('shows a missing README and unknown signals as unavailable', async () => {
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/recommendations/7': () =>
        json({ ...DETAIL, readme_excerpt: '', activity_signals: null }),
    })
    renderRoute('/app/recommendations/7')
    expect(await screen.findByText('No README available.')).toBeInTheDocument()
    const github = screen.getByRole('region', { name: 'From GitHub' })
    expect(within(github).getAllByText('Not available').length).toBeGreaterThan(0)
  })

  it('lists relevant issues under ContribFinder analysis', async () => {
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/recommendations/7': () =>
        json({
          ...DETAIL,
          relevant_issue_count: 2,
          issues: [
            {
              id: 31,
              number: 12,
              title: 'Fix typo in the Django guide',
              url: 'https://github.com/encode/httpx/issues/12',
              labels: ['good_first_issue', 'documentation'],
              contribution_type: 'documentation',
              difficulty: 'beginner',
              reasons: [
                { type: 'technology', text: 'Mentions Django, which you use', detail: {} },
                { type: 'approachability', text: 'Labeled "good first issue"', detail: {} },
              ],
            },
            {
              id: 32,
              number: 13,
              title: 'Crash on startup',
              url: 'https://github.com/encode/httpx/issues/13',
              labels: ['bug'],
              contribution_type: 'bug_fix',
              difficulty: 'unknown',
              reasons: [{ type: 'technology', text: 'Mentions Python, which you use', detail: {} }],
            },
          ],
        }),
    })
    renderRoute('/app/recommendations/7')

    const analysis = await screen.findByRole('region', { name: 'ContribFinder analysis' })
    const issues = within(analysis).getByRole('list', { name: 'Relevant issues' })
    const items = within(issues).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(
      within(items[0]).getByRole('link', { name: '#12 Fix typo in the Django guide' }),
    ).toHaveAttribute('href', '/app/issues/31')
    expect(items[0]).toHaveTextContent('Type: Documentation · Difficulty: Beginner (estimated)')
    expect(items[0]).toHaveTextContent('Mentions Django, which you use')
    expect(items[0]).not.toHaveTextContent('good first issue') // only the top reason
    expect(items[1]).toHaveTextContent('Type: Bug fix · Difficulty: Not enough evidence')
  })

  it('says when no relevant issues were found', async () => {
    mockFetch({ ...ME_ROUTE, 'GET /api/v1/recommendations/7': () => json(DETAIL) })
    renderRoute('/app/recommendations/7')
    const analysis = await screen.findByRole('region', { name: 'ContribFinder analysis' })
    expect(
      within(analysis).getByText(
        'No open issues matching your profile were found in this project.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'From GitHub' })).toBeInTheDocument()
  })

  it('explains a recommendation that no longer exists', async () => {
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/recommendations/7': () =>
        json({ error: { code: 'not_found', message: 'Not found.' } }, 404),
    })
    renderRoute('/app/recommendations/7')
    expect(await screen.findByRole('alert')).toHaveTextContent(/no longer exists/)
  })
})
