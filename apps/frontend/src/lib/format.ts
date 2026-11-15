const mediumDate = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const mediumDateTime = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})
const shortTime = new Intl.DateTimeFormat(undefined, { timeStyle: 'short' })

/** The time as a `Date`, or null when the browser cannot read it (CMP-1). */
function parse(time: string | Date): Date | null {
  const date = new Date(time)
  return Number.isNaN(date.getTime()) ? null : date
}

const UNKNOWN = 'Unknown'

/** A stored time (ISO 8601) or a `Date` as a medium date in the user's locale; "Unknown" for a
 * time that cannot be read. */
export function formatDate(time: string | Date): string {
  const date = parse(time)
  return date ? mediumDate.format(date) : UNKNOWN
}

/** A medium date and short time ("Nov 3, 2026, 14:05"). */
export function formatDateTime(time: string | Date): string {
  const date = parse(time)
  return date ? mediumDateTime.format(date) : UNKNOWN
}

/** A short time of day ("14:05"). */
export function formatTime(time: string | Date): string {
  const date = parse(time)
  return date ? shortTime.format(date) : UNKNOWN
}

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
// Each unit, its size in seconds and how many of it make the next larger unit.
const UNITS: [Intl.RelativeTimeFormatUnit, number, number][] = [
  ['minute', 60, 60],
  ['hour', 3_600, 24],
  ['day', 86_400, Infinity],
]

/** A past time relative to `now` in the user's locale ("5 minutes ago"). A time ahead of `now`
 * (clock skew) reads as now, never as the future; an unreadable time is "Unknown". The unit is
 * chosen after rounding, so 59.5 minutes reads as "1 hour ago", never "60 minutes ago". */
export function formatRelative(time: string | Date, now: number = Date.now()): string {
  const date = parse(time)
  if (!date) return UNKNOWN
  const seconds = Math.max(0, Math.round((now - date.getTime()) / 1000))
  if (seconds < 60) return relative.format(0, 'minute')
  for (const [unit, size, next] of UNITS) {
    const count = Math.round(seconds / size)
    if (count < next) return relative.format(-count, unit)
  }
  return relative.format(0, 'minute') // unreachable: days have no larger unit
}
