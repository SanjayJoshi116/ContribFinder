import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ME,
  NEVER_GENERATED,
  SYNCED_USER,
  changingVersions,
  json,
  mockFetch,
  renderRoute,
} from '@/test/render'

import { recommendationStatusKey, recommendationsPath } from './api'
import { shareText } from './messages'
import { listPath } from './navigation'

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
  setup: { ci: true, tests: true, dev_environment: false, docker_compose: null },
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

  it('shows the setup facts found, and nothing when none was found or they are unknown', async () => {
    const none = { ci: false, tests: false, dev_environment: false, docker_compose: false }
    const unknown = { ci: null, tests: null, dev_environment: null, docker_compose: null }
    const other = (id: number, name: string, setup: object) => ({
      ...RECOMMENDATION,
      id,
      repository: { ...REPOSITORY, name, full_name: `encode/${name}` },
      setup,
    })
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () => json(GENERATED),
      'GET /api/v1/recommendations': () =>
        page([RECOMMENDATION, other(8, 'starlette', none), other(9, 'uvicorn', unknown)]),
    })
    renderRoute('/app')

    const card = await screen.findByRole('article', { name: 'httpx' })
    expect(within(card).getByText('CI · tests')).toBeInTheDocument()
    expect(within(card).queryByText(/dev container|Docker Compose/)).not.toBeInTheDocument()
    for (const name of ['starlette', 'uvicorn']) {
      const plain = screen.getByRole('article', { name })
      expect(within(plain).queryByText(/CI|tests/)).not.toBeInTheDocument()
    }
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
    const versions = changingVersions()
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      ...versions.route,
      'GET /api/v1/recommendations/status': () => {
        statusCalls += 1
        if (statusCalls === 1) {
          return json({ ...NEVER_GENERATED, job: { ...GENERATED.job, status: 'RUNNING' } })
        }
        if (statusCalls === 2) versions.change('recommendations')
        return json(GENERATED)
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
    const versions = changingVersions()
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      ...versions.route,
      'GET /api/v1/recommendations/status': () => {
        statusCalls += 1
        if (statusCalls === 1) return json(NEVER_GENERATED)
        if (statusCalls === 2) versions.change('recommendations')
        return json(GENERATED)
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

  it('moves a page past the end to the first page', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/recommendations/status': () => json(GENERATED),
      'GET /api/v1/recommendations?page=5': () =>
        json({ error: { code: 'not_found', message: 'Invalid page.' } }, 404),
      'GET /api/v1/recommendations': () => page([RECOMMENDATION]),
    })
    const { router } = renderRoute('/app?page=5')

    expect(await screen.findByRole('article', { name: 'httpx' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
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
    // No score as a percentage: the only percentages are the language shares.
    const languages = screen.getByRole('list', { name: 'Languages by amount of code' })
    expect(within(languages).getByText('95%')).toBeInTheDocument()
    languages.remove()
    expect(document.body.textContent).not.toMatch(/%/)
  })

  it('shows setup facts as found, not found or not available, never "No"', async () => {
    mockFetch({ ...ME_ROUTE, 'GET /api/v1/recommendations/7': () => json(DETAIL) })
    renderRoute('/app/recommendations/7')

    const heading = await screen.findByRole('heading', { name: 'Setup' })
    const facts = heading.parentElement!
    const value = (term: string) => within(facts).getByText(term).nextElementSibling?.textContent
    expect(value('CI configuration')).toBe('Found')
    expect(value('Tests')).toBe('Found')
    expect(value('Dev container or Gitpod')).toBe('Not found')
    expect(value('Docker Compose')).toBe('Not available')
    expect(within(facts).queryByText('No')).not.toBeInTheDocument()
    expect(within(facts).getByText(/repository root only/)).toBeInTheDocument()
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

  it.each([
    [false, 'smooth'],
    [true, 'auto'],
  ])(
    'scrolls to and focuses the relevant issues from the card link (reduced motion: %s)',
    async (reduced, behavior) => {
      // jsdom implements neither.
      const scrollIntoView = vi.fn()
      Element.prototype.scrollIntoView = scrollIntoView
      vi.stubGlobal(
        'matchMedia',
        (query: string) => ({ matches: reduced && query.includes('reduce') }) as MediaQueryList,
      )
      try {
        mockFetch({ ...ME_ROUTE, 'GET /api/v1/recommendations/7': () => json(DETAIL) })
        renderRoute('/app/recommendations/7#relevant-issues')

        const heading = await screen.findByRole('heading', { name: 'Relevant issues' })
        await waitFor(() => expect(heading).toHaveFocus())
        expect(scrollIntoView).toHaveBeenCalledTimes(1)
        expect(scrollIntoView).toHaveBeenCalledWith({ block: 'start', behavior })
      } finally {
        delete (Element.prototype as Partial<Element>).scrollIntoView
      }
    },
  )

  it('shows the page for a malformed hash', async () => {
    mockFetch({ ...ME_ROUTE, 'GET /api/v1/recommendations/7': () => json(DETAIL) })
    renderRoute('/app/recommendations/7#%E0')

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('encode/httpx')
  })

  it.each([
    ['/app/recommendations/abc', "This link doesn't point to a recommendation."],
    ['/app/recommendations/0', "This link doesn't point to a recommendation."],
    ['/app/recommendations/0x1f', "This link doesn't point to a recommendation."],
    ['/app/issues/x', "This link doesn't point to an issue."],
    ['/app/issues/1e2', "This link doesn't point to an issue."],
  ])('says %s points to nothing, without a request', async (path, message) => {
    const fetchMock = mockFetch(ME_ROUTE)
    renderRoute(path)

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByRole('link', { name: 'Back to your dashboard' })).toHaveAttribute(
      'href',
      '/app',
    )
    // /auth/me only, besides the signed-in layout's data versions.
    const urls = fetchMock.mock.calls.map(([input]) => String(input))
    expect(urls.filter((url) => url !== '/api/v1/sync/versions')).toEqual(['/api/v1/auth/me'])
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

// --- review fixes (recommendations-view-review-fixes, REC-1…REC-9) -----------------------------

const STARLETTE = {
  ...RECOMMENDATION,
  id: 8,
  repository: { ...REPOSITORY, name: 'starlette', full_name: 'encode/starlette' },
}

const LIST_ROUTES = {
  ...ME_ROUTE,
  ...SYNCED_USER,
  'GET /api/v1/recommendations/status': () => json({ ...GENERATED, count: 25 }),
}

describe('recommendation list review fixes', () => {
  beforeEach(() => {
    document.cookie = 'csrftoken=test-csrf-token'
  })

  it('shows a filter value outside the options and clears it', async () => {
    mockFetch({
      ...LIST_ROUTES,
      'GET /api/v1/recommendations?language=ruby': () => page([]),
      'GET /api/v1/recommendations': () => page([RECOMMENDATION]),
    })
    const { router } = renderRoute('/app?language=ruby')
    expect(await screen.findByText('No recommendations match these filters.')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Language' })).toHaveValue('ruby')

    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))

    expect(await screen.findByRole('article', { name: 'httpx' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('')
  })

  it('offers Clear filters beside the invalid-filter message', async () => {
    mockFetch({
      ...LIST_ROUTES,
      'GET /api/v1/recommendations?match=foo': () =>
        json({ error: { code: 'validation_error', message: 'Invalid filter.' } }, 400),
      'GET /api/v1/recommendations': () => page([RECOMMENDATION]),
    })
    const { router } = renderRoute('/app?match=foo')
    expect(await screen.findByRole('alert')).toHaveTextContent(/filters are not valid/)

    const [, inAlert] = screen.getAllByRole('button', { name: 'Clear filters' })
    await userEvent.click(inAlert!)

    expect(await screen.findByRole('article', { name: 'httpx' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('')
  })

  it('lists every size the backend filters on', async () => {
    mockFetch({ ...LIST_ROUTES, 'GET /api/v1/recommendations': () => page([RECOMMENDATION]) })
    renderRoute('/app')
    await screen.findByRole('article', { name: 'httpx' })
    const size = screen.getByRole('combobox', { name: 'Size' })
    expect(
      within(size)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['Any', 'Small project', 'Medium project', 'Large project', 'Size unknown'])
  })

  it('shows the following recommendations once page 1 is emptied by a dismissal', async () => {
    let dismissed = false
    mockFetch({
      ...LIST_ROUTES,
      'GET /api/v1/recommendations': () =>
        dismissed
          ? page([STARLETTE])
          : page([RECOMMENDATION], { count: 21, next: '/api/v1/recommendations?page=2' }),
      'POST /api/v1/recommendations/7/dismiss': () => {
        dismissed = true
        return new Response(null, { status: 204 })
      },
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })

    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }))

    expect(await screen.findByRole('article', { name: 'starlette' })).toBeInTheDocument()
    expect(screen.queryByText(/no suitable projects/i)).not.toBeInTheDocument()
  })

  it('says Loading, not empty, while the dismissal of the only card is pending', async () => {
    mockFetch({
      ...LIST_ROUTES,
      'GET /api/v1/recommendations': () => page([RECOMMENDATION]),
      'POST /api/v1/recommendations/7/dismiss': () => new Promise<Response>(() => {}),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })

    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }))

    await waitFor(() =>
      expect(screen.queryByRole('article', { name: 'httpx' })).not.toBeInTheDocument(),
    )
    expect(screen.getByText('Loading…')).toBeInTheDocument()
    expect(screen.queryByText(/no suitable projects/i)).not.toBeInTheDocument()
  })

  it('offers the undo from the detail page once', async () => {
    mockFetch({ ...LIST_ROUTES, 'GET /api/v1/recommendations': () => page([STARLETTE]) })
    const { router } = renderRoute({
      pathname: '/app',
      state: { dismissed: { repositoryId: 70, name: 'encode/httpx' } },
    })

    expect(await screen.findByText(/hidden encode\/httpx/i)).toBeInTheDocument()
    await waitFor(() => expect(router.state.location.state).toBeNull())

    // Leave and come back through the history: the entry no longer carries the dismissal.
    await act(() => router.navigate('/app/recommendations/abc'))
    expect(await screen.findByText(/doesn't point to a recommendation/i)).toBeInTheDocument()
    await act(() => router.navigate(-1))
    expect(await screen.findByRole('article', { name: 'starlette' })).toBeInTheDocument()
    expect(screen.queryByText(/hidden encode\/httpx/i)).not.toBeInTheDocument()
  })

  it('marks old results as loading and disables the page buttons until the page arrives', async () => {
    let arrive: (response: Response) => void = () => {}
    mockFetch({
      ...LIST_ROUTES,
      'GET /api/v1/recommendations': () =>
        page([RECOMMENDATION], { count: 21, next: '/api/v1/recommendations?page=2' }),
      'GET /api/v1/recommendations?page=2': () =>
        new Promise<Response>((resolve) => {
          arrive = resolve
        }),
    })
    renderRoute('/app')
    const card = await screen.findByRole('article', { name: 'httpx' })
    expect(card.closest('[aria-busy]')).toHaveAttribute('aria-busy', 'false')

    await userEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled())
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
    expect(card.closest('[aria-busy]')).toHaveAttribute('aria-busy', 'true')

    arrive(
      new Response(
        JSON.stringify({
          count: 21,
          next: null,
          previous: '/api/v1/recommendations',
          results: [STARLETTE],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    expect(await screen.findByRole('article', { name: 'starlette' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeEnabled()
  })
})

describe('detail page review fixes', () => {
  beforeEach(() => {
    document.cookie = 'csrftoken=test-csrf-token'
  })

  it('returns to the list page and filters it was opened from, also after dismissing', async () => {
    let dismissed = false
    const listPage = '/api/v1/recommendations?language=rust&page=3'
    mockFetch({
      ...LIST_ROUTES,
      [`GET ${listPage}`]: () =>
        page(dismissed ? [STARLETTE] : [RECOMMENDATION], {
          count: 41,
          previous: '/api/v1/recommendations?language=rust&page=2',
        }),
      'GET /api/v1/recommendations/7': () => json(DETAIL),
      'POST /api/v1/recommendations/7/feedback': () => new Response(null, { status: 204 }),
      'POST /api/v1/recommendations/7/dismiss': () => {
        dismissed = true
        return new Response(null, { status: 204 })
      },
    })
    const { router } = renderRoute('/app?language=rust&page=3')
    await userEvent.click(await screen.findByRole('link', { name: 'httpx' }))

    const back = await screen.findByRole('link', { name: '← Back to recommendations' })
    expect(back).toHaveAttribute('href', '/app?language=rust&page=3')

    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }))

    expect(await screen.findByText(/hidden encode\/httpx/i)).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/app')
    expect(router.state.location.search).toBe('?language=rust&page=3')
    expect(await screen.findByRole('article', { name: 'starlette' })).toBeInTheDocument()
  })

  it.each([
    ['without navigation state', null],
    ['with a from that is not a search string', { from: '//example.com' }],
  ])('goes back to the first page %s', async (_case, state) => {
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/recommendations/7': () => json(DETAIL),
      'POST /api/v1/recommendations/7/feedback': () => new Response(null, { status: 204 }),
    })
    renderRoute({ pathname: '/app/recommendations/7', state })
    const back = await screen.findByRole('link', { name: '← Back to recommendations' })
    expect(back).toHaveAttribute('href', '/app')
  })

  it('gives each language share as text', async () => {
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/recommendations/7': () =>
        json({
          ...DETAIL,
          languages: [
            { language: 'Python', share: 0.52 },
            { language: 'Shell', share: 0.476 },
            { language: 'Dockerfile', share: 0.004 },
          ],
        }),
      'POST /api/v1/recommendations/7/feedback': () => new Response(null, { status: 204 }),
    })
    renderRoute('/app/recommendations/7')
    const languages = await screen.findByRole('list', { name: 'Languages by amount of code' })
    expect(
      within(languages)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Python52%', 'Shell48%', 'Dockerfileunder 1%'])
  })
})

describe('list return path and share text', () => {
  it('builds the way back from navigation state', () => {
    expect(listPath({ from: '?language=rust&page=3' })).toBe('/app?language=rust&page=3')
    expect(listPath({ from: '' })).toBe('/app')
    expect(listPath({ from: '//example.com' })).toBe('/app')
    expect(listPath({ from: 3 })).toBe('/app')
    expect(listPath(null)).toBe('/app')
    expect(listPath(undefined)).toBe('/app')
  })

  it('writes shares as whole percentages, under 1% below half a percent', () => {
    expect([0.52, 0.476, 0.005, 0.004, 0].map(shareText)).toEqual([
      '52%',
      '48%',
      '1%',
      'under 1%',
      'under 1%',
    ])
  })
})
