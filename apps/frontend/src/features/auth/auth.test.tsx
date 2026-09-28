import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ME, json, mockFetch, noContent, renderRoute, unauthenticated } from '@/test/render'

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

  it(
    'shows an error instead of redirecting on non-auth failures',
    { timeout: 10_000 },
    async () => {
      mockFetch({
        'GET /api/v1/auth/me': () => json({ error: { code: 'server_error', message: 'x' } }, 500),
      })
      const { router } = renderRoute('/app')

      // useMe retries non-401 failures twice with backoff before surfacing the error.
      expect(await screen.findByRole('alert', {}, { timeout: 6000 })).toHaveTextContent(
        /something went wrong/i,
      )
      expect(router.state.location.pathname).toBe('/app')
    },
  )
})

describe('signed-in shell', () => {
  it('renders the GitHub identity', async () => {
    mockFetch({ 'GET /api/v1/auth/me': () => json(ME) })
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
      'POST /api/v1/auth/logout': () => {
        signedIn = false
        return noContent()
      },
    })
    const { router } = renderRoute('/app')

    await userEvent.click(await screen.findByRole('button', { name: /log out/i }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    const [, init] = fetchMock.mock.calls.find(([, i]) => i?.method === 'POST')!
    expect(new Headers(init!.headers).get('X-CSRFToken')).toBe('test-csrf-token')
    expect(init!.credentials).toBe('same-origin')
  })

  it('disconnects GitHub only after confirmation, with a CSRF header', async () => {
    let signedIn = true
    const fetchMock = mockFetch({
      'GET /api/v1/auth/me': () => (signedIn ? json(ME) : unauthenticated()),
      'POST /api/v1/auth/github/disconnect': () => {
        signedIn = false
        return json({ revocation: 'revoked' })
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

  it('fetches a CSRF cookie first when none is present', async () => {
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
    const fetchMock = mockFetch({
      'GET /api/v1/auth/me': () => json(ME),
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
