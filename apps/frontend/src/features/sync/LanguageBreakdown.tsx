import type { Repository } from '@/api/types'

import { aggregateLanguages } from './languages'

const MAX_ROWS = 8

export function LanguageBreakdown({ repositories }: { repositories: readonly Repository[] }) {
  const shares = aggregateLanguages(repositories)
  if (shares.length === 0) {
    return <p className="text-muted-foreground text-sm">No languages detected yet.</p>
  }
  return (
    <ul className="space-y-2" aria-label="Languages">
      {shares.slice(0, MAX_ROWS).map(({ language, share }) => {
        const percent = Math.round(share * 1000) / 10
        return (
          <li key={language} className="grid grid-cols-[7rem_1fr_3.5rem] items-center gap-3">
            <span className="truncate text-sm">{language}</span>
            <span className="bg-secondary h-2 overflow-hidden rounded-full">
              <span
                className="bg-primary block h-full rounded-full"
                style={{ width: `${Math.max(percent, 1)}%` }}
              />
            </span>
            <span className="text-muted-foreground text-right text-sm tabular-nums">
              {percent}%
            </span>
          </li>
        )
      })}
    </ul>
  )
}
