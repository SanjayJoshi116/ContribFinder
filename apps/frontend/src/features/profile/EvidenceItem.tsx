import type { DeveloperSkill } from '@/api/types'
import { ExternalLink } from '@/components/ExternalLink'
import { formatDate } from '@/lib/format'

type Repository = DeveloperSkill['evidence'][number]['repository']

/** One evidence record: its source, supporting repository, detail and when it was observed. */
export function EvidenceItem({
  label,
  repository,
  detail,
  observedAt,
}: {
  label: string
  repository: Repository
  detail: string
  observedAt: string | null
}) {
  return (
    <li className="text-muted-foreground">
      <span className="text-foreground">{label}</span>
      {repository && (
        <>
          {' · '}
          <ExternalLink href={repository.html_url} className="hover:underline">
            {repository.full_name}
          </ExternalLink>
        </>
      )}
      {detail && ` · ${detail}`}
      {observedAt && ` · ${formatDate(observedAt)}`}
    </li>
  )
}
