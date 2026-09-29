import type { Repository } from '@/api/types'

export interface LanguageShare {
  language: string
  bytes: number
  share: number
}

/** Sum language bytes across repositories; largest first, shares add up to 1. */
export function aggregateLanguages(repositories: readonly Repository[]): LanguageShare[] {
  const totals = new Map<string, number>()
  for (const repo of repositories) {
    for (const { language, bytes } of repo.languages) {
      totals.set(language, (totals.get(language) ?? 0) + bytes)
    }
  }
  const sum = [...totals.values()].reduce((a, b) => a + b, 0)
  if (sum === 0) return []
  return [...totals.entries()]
    .map(([language, bytes]) => ({ language, bytes, share: bytes / sum }))
    .sort((a, b) => b.bytes - a.bytes || a.language.localeCompare(b.language))
}
