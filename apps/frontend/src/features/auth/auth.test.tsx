import type { QueryClient } from '@tanstack/react-query'
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ME,
  SYNCED_USER,
  json,
  mockFetch,
  noContent,
  renderRoute,
  unauthenticated,
} from '@/test/render'

import { meQueryKey } from './api'

/** Queries still cached under `prefix`. */
const cached = (queryClient: QueryClient, prefix: string) =>
  queryClient.getQueryCache().findAll({ queryKey: [prefix] }).length

/** Refetches the identity as a focus or a remount would. */
const refreshIdentity = (queryClient: QueryClient) =>
  act(() => queryClient.refetchQueries({ queryKey: meQueryKey }).catch(() => undefined))

beforeEach(() => {
  document.cookie = 'csrftoken=test-csrf-token'
})

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('landing page', () => {
  it('renders the GitHub sign-in call to action', async () => {
    mockFetch({ 'GET /api/v1/auth/me': unauthenticated })
    renderRoute('/')

    const cta = await screen.findByRole('link', { name: /continue with github/i })
    expect(cta).toHaveAttribute('href', '/api/v1/auth/github')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it.each([
    ['cancelled', /sign-in was cancelled/i],
    ['invalid_state', /expired or was interrupted/i],
    ['failed', /could not complete sign-in/i],
    ['something_unknown', /could not complete sign-in/i],
    ['__proto__', /could not complete sign-in/i],
    ['constructor', /could not complete sign-in/i],
    ['toString', /could not complete sign-in/i],
  ])('shows a readable message for auth_error=%s', async (code, message) => {
    mockFetch({ 'GET /api/v1/auth/me': unauthenticated })
    renderRoute(`/?auth_error=${code}`)

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })

  it('sends signed-in users to the app', async () => {
    mockFetch({ 'GET /api/v1/auth/me': () => json(ME) })
    const { router } = renderRoute('/')

    await waitFor(() => expect(router.state.location.pathname).toBe('/app'))
  })
})

describe('route guard', () => {
  it('redirects to the landing page when /me is 401', async () => {
    mockFetch({ 'GET /api/v1/auth/me': unauthenticated })
    const { router } = renderRoute('/app')

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    expect(await screen.findByRole('link', { name: /continue with github/i })).toBeInTheDocument()
  })

  it('shows an error instead of redirecting on non-auth failures', async () => {
    const fetchMock = mockFetch({
      'GET /api/v1/auth/me': () => json({ error: { code: 'server_error', message: 'x' } }, 500),
    })
    const { router } = renderRoute('/app')

    // A server error is retried twice before it is shown.
    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(router.state.location.pathname).toBe('/app')
  })

  it('keeps the signed-in page when a refresh of /me fails', async () => {
    let failing = false
    mockFetch({
      'GET /api/v1/auth/me': () =>
        failing ? json({ error: { code: 'server_error', message: 'x' } }, 503) : json(ME),
      ...SYNCED_USER,
    })
    const { router, queryClient } = renderRoute('/app')
    expect(await screen.findByRole('heading', { name: /welcome/i })).toBeInTheDocument()

    failing = true
    await refreshIdentity(queryClient)

    expect(screen.getByRole('heading', { name: /welcome/i })).toBeInTheDocument()
    expect(screen.queryByText(/something went wrong loading/i)).not.toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/app')
  })

  it('ends the session when a refresh of /me answers 401', async () => {
    let signedIn = true
    mockFetch({
      'GET /api/v1/auth/me': () => (signedIn ? json(ME) : unauthenticated()),
      ...SYNCED_USER,
    })
    const { router, queryClient } = renderRoute('/app')
    expect(await screen.findByRole('heading', { name: /welcome/i })).toBeInTheDocument()

    signedIn = false
    await refreshIdentity(queryClient)

    expect(await screen.findByRole('alert')).toHaveTextContent(/session ended/i)
    expect(router.state.location.search).toBe('?auth_error=session_ended')
    expect(cached(queryClient, 'profile')).toBe(0)
  })

  it('shows no session notice to a signed-out visitor', async () => {
    mockFetch({ 'GET /api/v1/auth/me': unauthenticated })
    renderRoute('/app')

    expect(await screen.findByRole('link', { name: /continue with github/i })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('signed-in shell', () => {
  it('renders the GitHub identity', async () => {
    mockFetch({ 'GET /api/v1/auth/me': () => json(ME), ...SYNCED_USER })
    renderRoute('/app')

    expect(
      await screen.findByRole('heading', { name: /welcome, the octocat/i }),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/octocat/).length).toBeGreaterThan(0)
  })

  it('logs out with a CSRF header and returns to the landing page', async () => {
    let signedIn = true
    const fetchMock = mockFetch({
      'GET /api/v1/auth/me': () => (signedIn ? json(ME) : unauthenticated()),
      ...SYNCED_USER,
      'POST /api/v1/auth/logout': () => {
        signedIn = false
        return noContent()
      },
    })
    const { router, queryClient } = renderRoute('/app')
    expect(await screen.findByRole('heading', { name: /welcome/i })).toBeInTheDocument()
    expect(cached(queryClient, 'profile')).toBeGreaterThan(0)

    await userEvent.click(await screen.findByRole('button', { name: /log out/i }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    const [, init] = fetchMock.mock.calls.find(([, i]) => i?.method === 'POST')!
    expect(new Headers(init!.headers).get('X-CSRFToken')).toBe('test-csrf-token')
    expect(init!.credentials).toBe('same-origin')
    expect(await screen.findByRole('link', { name: /continue with github/i })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(router.state.location.search).toBe('')
    expect(cached(queryClient, 'profile')).toBe(0)
    expect(cached(queryClient, 'jobs')).toBe(0)
  })

  it('disconnects GitHub only after confirmation, with a CSRF header', async () => {
    let signedIn = true
    const fetchMock = mockFetch({
      'GET /api/v1/auth/me': () => (signedIn ? json(ME) : unauthenticated()),
      ...SYNCED_USER,
      'POST /api/v1/auth/github/disconnect': () => {
        signedIn = false
        return json({ revocation: 'queued' })
      },
    })
    const { router } = renderRoute('/app')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /disconnect github/i }))
    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toHaveTextContent(/revoke/i)
    expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(false)

    await user.click(screen.getByRole('button', { name: /^disconnect$/i }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    const [url, init] = fetchMock.mock.calls.find(([, i]) => i?.method === 'POST')!
    expect(url).toBe('/api/v1/auth/github/disconnect')
    expect(new Headers(init!.headers).get('X-CSRFToken')).toBe('test-csrf-token')
  })

  it('deletes the account and leaves no signed-in data cached', async () => {
    let signedIn = true
    mockFetch({
      'GET /api/v1/auth/me': () => (signedIn ? json(ME) : unauthenticated()),
      ...SYNCED_USER,
      'DELETE /api/v1/auth/account': () => {
        signedIn = false
        return noContent()
      },
    })
    const { router, queryClient } = renderRoute('/app')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Delete account' }))
    await user.click(
      within(await screen.findByRole('alertdialog')).getByRole('button', {
        name: 'Delete account',
      }),
    )

    expect(await screen.findByRole('link', { name: /continue with github/i })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(cached(queryClient, 'profile')).toBe(0)
    expect(cached(queryClient, 'jobs')).toBe(0)
  })

  it('runs one account action at a time', async () => {
    mockFetch({
      'GET /api/v1/auth/me': () => json(ME),
      ...SYNCED_USER,
      'DELETE /api/v1/auth/account': () => new Promise<Response>(() => undefined),
    })
    renderRoute('/app')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Delete account' }))
    await user.click(
      within(await screen.findByRole('alertdialog')).getByRole('button', {
        name: 'Delete account',
      }),
    )

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /disconnect github/i })).toBeDisabled(),
    )
    expect(screen.getByRole('button', { name: 'Delete GitHub data' })).toBeDisabled()
    expect(screen.getByRole('button', { name: /log out/i })).toBeDisabled()
  })

  it('fetches a CSRF cookie first when none is present', async () => {
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
    const fetchMock = mockFetch({
      'GET /api/v1/auth/me': () => json(ME),
      ...SYNCED_USER,
      'GET /api/v1/auth/csrf/': () => {
        document.cookie = 'csrftoken=fresh-token'
        return noContent()
      },
      'POST /api/v1/auth/logout': noContent,
    })
    renderRoute('/app')

    await userEvent.click(await screen.findByRole('button', { name: /log out/i }))

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(true),
    )
    const [, init] = fetchMock.mock.calls.find(([, i]) => i?.method === 'POST')!
    expect(new Headers(init!.headers).get('X-CSRFToken')).toBe('fresh-token')
  })
})
