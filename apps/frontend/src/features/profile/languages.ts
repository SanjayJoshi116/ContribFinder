import type { ProfileLanguage } from '@/api/types'

const MAX_ROWS = 8

export interface LanguageRow {
  name: string
  share: number
}

/** Top languages by bytes (sorted here, whatever the API's order); the rest are folded into
 * "Other" only when two or more are left, since one leftover is shown by name. Shares come from
 * bytes, not from the API's shares, which are rounded to 2 decimals: summing those loses small
 * languages. */
export function languageRows(languages: readonly ProfileLanguage[]): LanguageRow[] {
  const total = languages.reduce((sum, { bytes }) => sum + bytes, 0)
  if (total === 0) return []
  const sorted = [...languages].sort((a, b) => b.bytes - a.bytes || a.name.localeCompare(b.name))
  const row = ({ name, bytes }: ProfileLanguage) => ({ name, share: bytes / total })
  if (sorted.length <= MAX_ROWS + 1) return sorted.map(row)
  const rest = sorted.slice(MAX_ROWS).reduce((sum, { bytes }) => sum + bytes, 0)
  return [...sorted.slice(0, MAX_ROWS).map(row), { name: 'Other', share: rest / total }]
}

/** A share as a whole percentage; a nonzero share that would round to 0 shows as "<1%". */
export function percent(share: number): string {
  if (share > 0 && share < 0.005) return '<1%'
  return `${Math.round(share * 100)}%`
}
