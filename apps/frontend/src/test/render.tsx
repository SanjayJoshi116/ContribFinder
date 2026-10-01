import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { vi } from 'vitest'

import { routes } from '@/routes/routes'

export function renderRoute(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { ...utils, router, queryClient }
}

type Handler = (init: RequestInit | undefined) => Response | Promise<Response>

/** Stubs global fetch with per-"METHOD path" handlers; unmatched requests fail loudly. */
export function mockFetch(handlers: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = (init?.method ?? 'GET').toUpperCase()
    const handler = handlers[`${method} ${url}`]
    if (!handler) throw new Error(`Unexpected fetch: ${method} ${url}`)
    return handler(init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

export const noContent = () => new Response(null, { status: 204 })

export const unauthenticated = () =>
  json({ error: { code: 'not_authenticated', message: 'Not signed in.' } }, 401)

export const ME = {
  id: 1,
  github_username: 'octocat',
  display_name: 'The Octocat',
  avatar_url: 'https://avatars.example/1',
  github_connected: true,
}

export const REPO = {
  id: 11,
  full_name: 'octocat/tools',
  name: 'tools',
  owner_login: 'octocat',
  description: 'Developer tooling',
  html_url: 'https://github.com/octocat/tools',
  default_branch: 'main',
  stars: 5,
  forks: 1,
  open_issues: 0,
  primary_language: 'Python',
  license_spdx: 'MIT',
  is_fork: false,
  is_archived: false,
  github_created_at: '2020-01-01T00:00:00Z',
  github_updated_at: '2026-09-01T00:00:00Z',
  pushed_at: '2026-09-01T00:00:00Z',
  languages: [{ language: 'Python', bytes: 7000 }],
  topics: ['cli'],
}

export const PROFILE = {
  login: 'octocat',
  name: 'The Octocat',
  bio: 'Builds tools',
  company: '',
  location: '',
  blog: '',
  avatar_url: 'https://avatars.example/1',
  followers: 1,
  following: 0,
  public_repos: 1,
  github_created_at: '2011-01-25T18:44:36Z',
  has_profile_readme: true,
  synced_at: '2026-09-28T10:00:00Z',
}

export const COMPLETED_JOB = {
  id: 1,
  job_type: 'github_profile_sync',
  status: 'COMPLETED',
  steps: {
    profile: 'done',
    readme: 'done',
    repositories: 'done',
    languages: 'done',
    topics: 'done',
    dependencies: 'done',
    contributions: 'done',
    analysis: 'done',
  },
  attempts: 1,
  error_code: '',
  created_at: '2026-09-28T10:00:00Z',
  started_at: '2026-09-28T10:00:00Z',
  completed_at: '2026-09-28T10:00:05Z',
}

export const DEVELOPER_PROFILE = {
  summary: 'Works mostly in Python. Frequently uses Django. Interested in developer tooling.',
  languages: [
    { name: 'Python', bytes: 7000, share: 0.7, repo_count: 1 },
    { name: 'TypeScript', bytes: 3000, share: 0.3, repo_count: 1 },
  ],
  preferred_project_size: 'any',
  preferred_issue_difficulty: 'unknown',
  analyzed_at: '2026-09-28T10:00:05Z',
  skill_count: 2,
  interest_count: 1,
}

export const SKILLS = [
  {
    id: 1,
    skill: { slug: 'python', name: 'Python', category: 'language' },
    confidence: 0.93,
    evidence_summary: {
      by_source: { readme: 1, language: 8, dependency: 2 },
      repository_count: 8,
      last_observed_at: '2026-09-01T00:00:00Z',
    },
    evidence: [
      {
        source: 'readme',
        repository: null,
        detail: '"Skills" section',
        observed_at: null,
      },
      {
        source: 'language',
        repository: { full_name: 'octocat/tools', html_url: 'https://github.com/octocat/tools' },
        detail: 'Python · 90% of code',
        observed_at: '2026-09-01T00:00:00Z',
      },
    ],
  },
  {
    id: 2,
    skill: { slug: 'django', name: 'Django', category: 'framework' },
    confidence: 0.6,
    evidence_summary: {
      by_source: { dependency: 1 },
      repository_count: 1,
      last_observed_at: '2026-09-01T00:00:00Z',
    },
    evidence: [
      {
        source: 'dependency',
        repository: { full_name: 'octocat/tools', html_url: 'https://github.com/octocat/tools' },
        detail: 'pyproject.toml: django',
        observed_at: '2026-09-01T00:00:00Z',
      },
    ],
  },
]

export const INTERESTS = [
  {
    id: 1,
    interest: { slug: 'developer-tooling', name: 'Developer tooling' },
    strength: 0.5,
    evidence: [
      {
        source: 'topic',
        repository: { full_name: 'octocat/tools', html_url: 'https://github.com/octocat/tools' },
        detail: '"cli"',
        observed_at: '2026-09-01T00:00:00Z',
      },
    ],
  },
]

export const EMPTY_POOL = {
  total: 0,
  eligible: 0,
  awaiting_analysis: 0,
  ineligible: 0,
  by_source: {},
}

export const NEVER_DISCOVERED = { job: null, last_completed_at: null, pool: EMPTY_POOL }

export const NEVER_GENERATED = {
  job: null,
  last_generated_at: null,
  count: 0,
  config_version: null,
}

export function discoveryJob(status: string, error_code = '') {
  const done = status === 'COMPLETED'
  return {
    id: 2,
    job_type: 'repository_discovery',
    status,
    steps: {
      queries: done ? 'done' : 'running',
      search: done ? 'done' : 'pending',
      interactions: done ? 'done' : 'pending',
      analysis: done ? 'done' : 'pending',
      pool: done ? 'done' : 'pending',
    },
    attempts: 1,
    error_code,
    created_at: '2026-09-28T10:00:06Z',
    started_at: '2026-09-28T10:00:06Z',
    completed_at: done || status === 'FAILED' ? '2026-09-28T10:01:00Z' : null,
  }
}

const page = (results: unknown[]) =>
  json({ count: results.length, next: null, previous: null, results })

/** Handlers for a user whose GitHub data has been synced and analyzed. */
export const SYNCED_USER: Record<string, Handler> = {
  'GET /api/v1/sync/status': () =>
    json({ job: COMPLETED_JOB, last_synced_at: COMPLETED_JOB.completed_at }),
  'GET /api/v1/profile/github': () => json(PROFILE),
  'GET /api/v1/profile/repositories?page_size=100': () =>
    json({ count: 1, next: null, previous: null, results: [REPO] }),
  'GET /api/v1/profile': () => json(DEVELOPER_PROFILE),
  'GET /api/v1/profile/skills?page_size=200': () => page(SKILLS),
  'GET /api/v1/profile/interests?page_size=200': () => page(INTERESTS),
  'GET /api/v1/discovery/status': () => json(NEVER_DISCOVERED),
  'GET /api/v1/recommendations/status': () => json(NEVER_GENERATED),
  'GET /api/v1/recommendations': () => page([]),
}
