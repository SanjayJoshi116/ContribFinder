import { describe, expect, it } from 'vitest'

import { ApiError } from '@/api/client'

import { startErrorText } from './messages'

const AT = new Date(2026, 10, 3, 14, 1, 0).getTime()
const clock = (date: Date, options: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat(undefined, options).format(date)

describe('startErrorText', () => {
  it('names the clock time a cooldown ends', () => {
    const error = new ApiError(429, 'sync_cooldown', 'A sync ran recently.', undefined, 240)
    const time = clock(new Date(2026, 10, 3, 14, 5, 0), { timeStyle: 'short' })

    expect(startErrorText(error, AT)).toBe(
      `Your data was synced recently. You can refresh again after ${time}.`,
    )
  })

  it('adds the date when the cooldown ends on another day', () => {
    const late = new Date(2026, 10, 3, 23, 59, 0).getTime()
    const error = new ApiError(429, 'sync_cooldown', 'A sync ran recently.', undefined, 240)
    const when = clock(new Date(2026, 10, 4, 0, 3, 0), { dateStyle: 'medium', timeStyle: 'short' })

    expect(startErrorText(error, late)).toBe(
      `Your data was synced recently. You can refresh again after ${when}.`,
    )
  })

  it('shows the message of any other error', () => {
    expect(startErrorText(new ApiError(503, 'unavailable', 'Try later.'), AT)).toBe('Try later.')
    expect(startErrorText(new ApiError(429, 'sync_cooldown', 'Wait.'), AT)).toBe('Wait.')
  })
})
