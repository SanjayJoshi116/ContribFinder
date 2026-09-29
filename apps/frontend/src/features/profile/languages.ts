import type { ProfileLanguage } from '@/api/types'

const MAX_ROWS = 8

export interface LanguageRow {
  name: string
  share: number
}

/** Top languages by bytes; the rest are folded into "Other". */
export function languageRows(languages: readonly ProfileLanguage[]): LanguageRow[] {
  const top = languages.slice(0, MAX_ROWS).map(({ name, share }) => ({ name, share }))
  const rest = languages.slice(MAX_ROWS).reduce((sum, { share }) => sum + share, 0)
  return rest > 0 ? [...top, { name: 'Other', share: Math.round(rest * 100) / 100 }] : top
}
