import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'
import { callsTo, json, mockFetch, noContent } from '@/test/render'

const clearCookie = () => {
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
}

/** The rejection of `promise`, which must be an `ApiError`. */
async function failure(promise: Promise<unknown>): Promise<ApiError> {
  const error: unknown = await promise.then(
    () => undefined,
    (e: unknown) => e,
  )
  expect(error).toBeInstanceOf(ApiError)
  return error as ApiError
}

beforeEach(() => {
  document.cookie = 'csrftoken=test-csrf-token'
})

afterEach(() => {
  vi.unstubAllGlobals()
  clearCookie()
})

describe('apiFetch failures', () => {
  it('reports no response as network_error with status 0', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
    const error = await failure(apiFetch('/profile'))
    expect([error.status, error.code]).toEqual([0, 'network_error'])
  })

  it('reports a success body that is not JSON as invalid_response', async () => {
    mockFetch({ 'GET /api/v1/profile': () => new Response('<html>app</html>', { status: 200 }) })
    const error = await failure(apiFetch('/profile'))
    expect([error.status, error.code]).toEqual([200, 'invalid_response'])
  })

  it('lets an abort through as it is', async () => {
    const abort = new DOMException('Aborted', 'AbortError')
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(abort)),
    )
    await expect(apiFetch('/profile')).rejects.toBe(abort)
  })

  it('keeps the wait of an error without the envelope', async () => {
    mockFetch({
      'GET /api/v1/profile': () =>
        new Response('Service Unavailable', { status: 503, headers: { 'Retry-After': '30' } }),
    })
    const error = await failure(apiFetch('/profile'))
    expect([error.status, error.code, error.retryAfter]).toEqual([503, 'http_error', 30])
  })
})

describe('CSRF token request', () => {
  it("reports the token request's own error and sends nothing else", async () => {
    clearCookie()
    const fetchMock = mockFetch({
      'GET /api/v1/auth/csrf/': () =>
        json({ error: { code: 'throttled', message: 'Slow down.' } }, 429),
      'POST /api/v1/profile/sync': noContent,
    })
    const error = await failure(apiFetch('/profile/sync', { method: 'POST' }))
    expect([error.status, error.code]).toEqual([429, 'throttled'])
    expect(callsTo(fetchMock, 'POST', '/api/v1/profile/sync')).toHaveLength(0)
  })

  it('is shared by concurrent mutations', async () => {
    clearCookie()
    const fetchMock = mockFetch({
      'GET /api/v1/auth/csrf/': async () => {
        await new Promise((resolve) => setTimeout(resolve, 10))
        document.cookie = 'csrftoken=fresh-token'
        return noContent()
      },
      'POST /api/v1/recommendations/1/save': noContent,
      'POST /api/v1/recommendations/2/save': noContent,
    })
    await Promise.all([
      apiFetch('/recommendations/1/save', { method: 'POST' }),
      apiFetch('/recommendations/2/save', { method: 'POST' }),
    ])
    expect(callsTo(fetchMock, 'GET', '/api/v1/auth/csrf/')).toHaveLength(1)
    for (const n of [1, 2]) {
      const [[, init]] = callsTo(fetchMock, 'POST', `/api/v1/recommendations/${n}/save`)
      expect(new Headers(init!.headers).get('X-CSRFToken')).toBe('fresh-token')
    }
  })

  it('outlives the page with a keepalive request', async () => {
    clearCookie()
    const fetchMock = mockFetch({
      'GET /api/v1/auth/csrf/': () => {
        document.cookie = 'csrftoken=fresh-token'
        return noContent()
      },
      'POST /api/v1/recommendations/1/feedback': noContent,
    })
    await apiFetch('/recommendations/1/feedback', { method: 'POST', keepalive: true })
    const [[, prelude]] = callsTo(fetchMock, 'GET', '/api/v1/auth/csrf/')
    expect(prelude?.keepalive).toBe(true)
  })
})

describe('JSON bodies', () => {
  it('sends json with its content type', async () => {
    const fetchMock = mockFetch({ 'POST /api/v1/recommendations/1/dismiss': noContent })
    await apiFetch('/recommendations/1/dismiss', { method: 'POST', json: { reason: 'too_big' } })
    const [[, init]] = callsTo(fetchMock, 'POST', '/api/v1/recommendations/1/dismiss')
    expect(init?.body).toBe('{"reason":"too_big"}')
    expect(new Headers(init!.headers).get('Content-Type')).toBe('application/json')
  })
})
