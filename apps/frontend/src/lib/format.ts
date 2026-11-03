const mediumDate = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const mediumDateTime = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})
const shortTime = new Intl.DateTimeFormat(undefined, { timeStyle: 'short' })

/** A stored time (ISO 8601) or a `Date` as a medium date in the user's locale. */
export function formatDate(time: string | Date): string {
  return mediumDate.format(new Date(time))
}

/** A medium date and short time ("Nov 3, 2026, 14:05"). */
export function formatDateTime(time: string | Date): string {
  return mediumDateTime.format(new Date(time))
}

/** A short time of day ("14:05"). */
export function formatTime(time: string | Date): string {
  return shortTime.format(new Date(time))
}
