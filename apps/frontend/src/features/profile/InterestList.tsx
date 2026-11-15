import type { DeveloperInterest } from '@/api/types'

import { EvidenceItem } from './EvidenceItem'
import { INTEREST_SOURCE_LABELS } from './evidence'

export function InterestList({ interests }: { interests: readonly DeveloperInterest[] }) {
  if (interests.length === 0) {
    return <p className="text-muted-foreground text-sm">No interests detected yet.</p>
  }
  return (
    <ul className="space-y-2" aria-label="Interests">
      {/* By slug: a re-analysis recreates the rows with new ids. */}
      {interests.map(({ interest, evidence }) => (
        <li key={interest.slug}>
          <details className="rounded-lg border px-3 py-2">
            <summary className="cursor-pointer text-sm">
              <span className="font-medium">{interest.name}</span>
              <span className="text-muted-foreground">
                {' '}
                · {evidence.length} {evidence.length === 1 ? 'signal' : 'signals'}
              </span>
            </summary>
            <ul className="mt-2 space-y-1 text-sm" aria-label={`Evidence for ${interest.name}`}>
              {evidence.map((item, index) => (
                <EvidenceItem
                  key={index}
                  label={INTEREST_SOURCE_LABELS[item.source]}
                  repository={item.repository}
                  detail={item.detail}
                  observedAt={item.observed_at}
                />
              ))}
            </ul>
          </details>
        </li>
      ))}
    </ul>
  )
}
