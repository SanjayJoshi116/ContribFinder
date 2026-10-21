import type { ProfileLanguage } from '@/api/types'

const MAX_ROWS = 8

export interface LanguageRow {
  name: string
  share: number
}

/** Top languages by bytes; the rest are folded into "Other". Shares come from bytes, not from
 * the API's shares, which are rounded to 2 decimals: summing those loses small languages. */
export function languageRows(languages: readonly ProfileLanguage[]): LanguageRow[] {
  const total = languages.reduce((sum, { bytes }) => sum + bytes, 0)
  if (total === 0) return []
  const top = languages
    .slice(0, MAX_ROWS)
    .map(({ name, bytes }) => ({ name, share: bytes / total }))
  const rest = languages.slice(MAX_ROWS).reduce((sum, { bytes }) => sum + bytes, 0)
  return rest > 0 ? [...top, { name: 'Other', share: rest / total }] : top
}

/** A share as a whole percentage; a nonzero share that would round to 0 shows as "<1%". */
export function percent(share: number): string {
  if (share > 0 && share < 0.005) return '<1%'
  return `${Math.round(share * 100)}%`
}
