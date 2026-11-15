import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DiscoveryStatus, SyncJob } from '@/api/types'
import {
  EMPTY_POOL,
  ME,
  NEVER_DISCOVERED,
  SYNCED_USER,
  discoveryJob,
  json,
  mockFetch,
  renderRoute,
} from '@/test/render'

import { formatRelative } from '@/lib/format'

import { describeDiscovery, discoveryFailure } from './messages'

const NOW = new Date('2026-09-28T12:00:00Z').getTime()
const POOL = { ...EMPTY_POOL, total: 120, eligible: 95, awaiting_analysis: 15, ineligible: 10 }

function status(job: SyncJob | null, completed: string | null = null): DiscoveryStatus {
  return { job, last_completed_at: completed, pool: POOL } as DiscoveryStatus
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('describeDiscovery', () => {
  it('reports an active run', () => {
    const message = describeDiscovery(status(discoveryJob('RUNNING') as SyncJob), NOW)
    expect(message).toEqual({ text: 'Finding projects that match your profile…', alert: false })
  })

  it('reports the eligible count and when discovery last completed', () => {
    const message = describeDiscovery(
      status(discoveryJob('COMPLETED') as SyncJob, '2026-09-28T10:00:00Z'),
      NOW,
    )
    expect(message.text).toBe('95 candidate projects found · updated 2 hours ago')
    expect(message.text).not.toMatch(/%/)
  })

  it('has a state before the first run', () => {
    expect(describeDiscovery(NEVER_DISCOVERED as DiscoveryStatus).text).toMatch(
      /after your profile is ready/,
    )
  })

  it('maps failure codes to readable messages', () => {
    expect(discoveryFailure(discoveryJob('FAILED', 'github_auth_invalid') as SyncJob)).toMatch(
      /sign in with github again/i,
    )
    expect(discoveryFailure(discoveryJob('FAILED', 'github_rate_limited') as SyncJob)).toMatch(
      /limiting requests/,
    )
    expect(discoveryFailure(discoveryJob('FAILED', 'weird') as SyncJob)).toMatch(
      /stopped unexpectedly/,
    )
  })

  it('formats relative times, never in the future', () => {
    expect(formatRelative('2026-09-28T11:59:40Z', NOW)).toBe('this minute')
    expect(formatRelative('2026-09-26T12:00:00Z', NOW)).toBe('2 days ago')
    // 90 s ahead (clock skew) reads as now.
    expect(formatRelative('2026-09-28T12:01:30Z', NOW)).toBe('this minute')
    // The unit is chosen after rounding: never "60 minutes" or "24 hours".
    expect(formatRelative('2026-09-28T11:00:01Z', NOW)).toBe('1 hour ago')
    expect(formatRelative('2026-09-27T12:00:01Z', NOW)).toBe('yesterday')
    expect(formatRelative('2026-09-28T11:15:00Z', NOW)).toBe('45 minutes ago')
  })

  it('gives a stalled run the stalled notice, not finding projects', () => {
    const job = { ...discoveryJob('RUNNING'), stalled: true } as SyncJob
    const { text } = describeDiscovery(status(job), NOW)
    expect(text).toMatch(/^Background work stopped/)
    expect(text).not.toMatch(/finding projects/i)
  })

  it('uses the shared GitHub reason, with its own next step', () => {
    expect(discoveryFailure(discoveryJob('FAILED', 'github_not_connected') as SyncJob)).toBe(
      'Your GitHub account is not connected. Sign in with GitHub to find projects.',
    )
  })
})

describe('discovery card', () => {
  const ME_ROUTE = { 'GET /api/v1/auth/me': () => json(ME) }

  it('moves from finding to completed without a reload', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let calls = 0
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/discovery/status': () => {
        calls += 1
        return calls === 1
          ? json(status(discoveryJob('RUNNING') as SyncJob))
          : json(status(discoveryJob('COMPLETED') as SyncJob, new Date().toISOString()))
      },
    })
    renderRoute('/app')

    const card = await screen.findByRole('region', { name: 'Project discovery' })
    expect(await within(card).findByText(/finding projects/i)).toBeInTheDocument()

    await vi.advanceTimersByTimeAsync(3100)
    expect(await within(card).findByText(/95 candidate projects found/)).toBeInTheDocument()
    expect(card.textContent).not.toMatch(/\d+\s*%/)
  })

  it('advances "updated …" while the card is shown', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/discovery/status': () =>
        json(status(discoveryJob('COMPLETED') as SyncJob, new Date().toISOString())),
    })
    renderRoute('/app')
    const card = await screen.findByRole('region', { name: 'Project discovery' })
    expect(await within(card).findByText(/updated this minute/)).toBeInTheDocument()

    await vi.advanceTimersByTimeAsync(60 * 60 * 1000)

    expect(await within(card).findByText(/updated 1 hour ago/)).toBeInTheDocument()
  })

  it('follows a running discovery while the profile is not analyzed yet', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let calls = 0
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/profile': () =>
        json({ error: { code: 'not_analyzed', message: 'Not built yet.' } }, 404),
      'GET /api/v1/discovery/status': () => {
        calls += 1
        return json(status(discoveryJob(calls === 1 ? 'RUNNING' : 'COMPLETED') as SyncJob))
      },
    })
    renderRoute('/app')

    expect(await screen.findByText('Finding projects…')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Project discovery' })).not.toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() => expect(screen.queryByText('Finding projects…')).not.toBeInTheDocument())
    expect(calls).toBeGreaterThanOrEqual(2)
  })

  it('shows a failure as an alert', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/discovery/status': () =>
        json(status(discoveryJob('FAILED', 'github_unavailable') as SyncJob)),
    })
    renderRoute('/app')
    const card = await screen.findByRole('region', { name: 'Project discovery' })
    expect(within(card).getByRole('alert')).toHaveTextContent(/not responding/)
  })
})
