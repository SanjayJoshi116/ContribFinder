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
  return { ...utils, router }
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
  },
  attempts: 1,
  error_code: '',
  created_at: '2026-09-28T10:00:00Z',
  started_at: '2026-09-28T10:00:00Z',
  completed_at: '2026-09-28T10:00:05Z',
}

/** Handlers for a user whose GitHub data has been synced. */
export const SYNCED_USER: Record<string, Handler> = {
  'GET /api/v1/sync/status': () =>
    json({ job: COMPLETED_JOB, last_synced_at: COMPLETED_JOB.completed_at }),
  'GET /api/v1/profile/github': () => json(PROFILE),
  'GET /api/v1/profile/repositories?page_size=100': () =>
    json({ count: 1, next: null, previous: null, results: [REPO] }),
}
