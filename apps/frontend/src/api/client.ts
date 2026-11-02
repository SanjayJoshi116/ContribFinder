import type { ApiErrorBody } from './types'

export const API_BASE = '/api/v1'
const CSRF_COOKIE = 'csrftoken'
const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: unknown
  /** Seconds from the Retry-After header (429 responses), when present. */
  readonly retryAfter?: number

  constructor(
    status: number,
    code: string,
    message: string,
    details?: unknown,
    retryAfter?: number,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.retryAfter = retryAfter
  }
}

export function readCookie(name: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1)
}

/** The request in flight for a CSRF cookie: concurrent mutations share it. */
let pendingCsrf: Promise<string> | null = null

/** The CSRF token, from the cookie or GET /auth/csrf/ (which sets it). A failed token request
 * reports its own status and code. `keepalive` lets the request outlive the page, as the
 * request that waits for it does. */
function csrfToken(keepalive: boolean): Promise<string> {
  const existing = readCookie(CSRF_COOKIE)
  if (existing) return Promise.resolve(existing)
  pendingCsrf ??= fetchCsrfToken(keepalive).finally(() => {
    pendingCsrf = null
  })
  return pendingCsrf
}

async function fetchCsrfToken(keepalive: boolean): Promise<string> {
  const response = await send(`${API_BASE}/auth/csrf/`, { credentials: 'same-origin', keepalive })
  if (!response.ok) throw await toApiError(response)
  const token = readCookie(CSRF_COOKIE)
  if (!token) throw new ApiError(0, 'csrf_unavailable', 'Could not obtain a CSRF token.')
  return token
}

/** `fetch`, with a failure before any response as `ApiError(0, 'network_error')`. An abort
 * passes through: TanStack Query reads it as a cancellation. */
async function send(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'Could not reach the server.')
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  const header = Number(response.headers.get('Retry-After'))
  const retryAfter = Number.isFinite(header) && header > 0 ? header : undefined
  try {
    const body = (await response.json()) as Partial<ApiErrorBody>
    if (body.error) {
      const { code, message, details } = body.error
      return new ApiError(response.status, code, message, details, retryAfter)
    }
  } catch {
    // Non-JSON error body; fall through to a generic error.
  }
  return new ApiError(
    response.status,
    'http_error',
    `Request failed with status ${response.status}`,
    undefined,
    retryAfter,
  )
}

/** `RequestInit` plus `json`: a body sent as JSON, with its `Content-Type`. */
export type ApiInit = Omit<RequestInit, 'body'> &
  ({ body?: BodyInit | null; json?: never } | { json: unknown; body?: never })

/** Every failure is an `ApiError`: the server's envelope, `http_error`, `network_error` (no
 * response) or `invalid_response` (a success whose body is not JSON). */
export async function apiFetch<T>(path: string, init: ApiInit = {}): Promise<T> {
  const { json, ...rest } = init
  const method = (rest.method ?? 'GET').toUpperCase()
  const headers = new Headers(rest.headers)
  headers.set('Accept', 'application/json')
  if (json !== undefined) headers.set('Content-Type', 'application/json')
  if (MUTATING.has(method)) {
    headers.set('X-CSRFToken', await csrfToken(rest.keepalive === true))
  }

  const response = await send(`${API_BASE}${path}`, {
    ...rest,
    ...(json !== undefined ? { body: JSON.stringify(json) } : {}),
    method,
    headers,
    credentials: 'same-origin',
  })
  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError(response.status, 'invalid_response', 'The server sent an unreadable answer.')
  }
}
