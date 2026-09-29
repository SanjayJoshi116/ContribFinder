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

/** Ensures the CSRF cookie exists (Django sets it on GET /auth/csrf/). */
export async function ensureCsrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE)
  if (existing) return existing
  await fetch(`${API_BASE}/auth/csrf/`, { credentials: 'same-origin' })
  const token = readCookie(CSRF_COOKIE)
  if (!token) throw new ApiError(0, 'csrf_unavailable', 'Could not obtain a CSRF token.')
  return token
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
  )
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (MUTATING.has(method)) {
    headers.set('X-CSRFToken', await ensureCsrfToken())
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    method,
    headers,
    credentials: 'same-origin',
  })
  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
