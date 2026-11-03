import { Link } from 'react-router'

import type { Recommendation } from '@/api/types'
import { ExternalLink } from '@/components/ExternalLink'
import { recordFeedback } from '@/features/feedback/api'
import {
  DismissButton,
  type DismissedProject,
  SaveButton,
} from '@/features/feedback/RecommendationActions'
import { cn } from '@/lib/utils'

import { ACTIVITY_TEXT, MATCH_TEXT, setupLine } from './messages'

const MAX_TECHNOLOGIES = 8
const MAX_REASONS = 3

export function MatchBadge({ label }: { label: Recommendation['match_label'] }) {
  return (
    <span
      className={cn(
        'rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        label === 'strong' && 'border-primary text-primary',
      )}
    >
      {MATCH_TEXT[label]}
    </span>
  )
}

export function TechnologyChips({
  technologies,
  limit,
}: {
  technologies: Recommendation['technologies']
  limit?: number
}) {
  const shown = limit ? technologies.slice(0, limit) : technologies
  if (shown.length === 0) return null
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Technologies">
      {shown.map((tech) => (
        <li
          key={tech.slug}
          className={cn(
            'rounded border px-1.5 py-0.5 text-xs',
            tech.matched ? 'bg-secondary font-medium' : 'text-muted-foreground',
          )}
          title={tech.matched ? 'In your profile' : undefined}
        >
          {tech.name}
          {tech.matched && <span className="sr-only"> (in your profile)</span>}
        </li>
      ))}
    </ul>
  )
}

/** Why a repository is recommended comes first; there is no score to show. */
export function RecommendationCard({
  recommendation,
  onDismissed,
}: {
  recommendation: Recommendation
  onDismissed: (project: DismissedProject) => void
}) {
  const { repository, reasons, activity_label } = recommendation
  const headingId = `recommendation-${recommendation.id}`
  const setup = setupLine(recommendation.setup)
  return (
    <article aria-labelledby={headingId} className="space-y-3 rounded-md border p-4">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 id={headingId} className="font-medium break-words">
            <Link to={`/app/recommendations/${recommendation.id}`} className="hover:underline">
              {repository.name}
            </Link>
          </h3>
          <p className="text-muted-foreground text-xs">{repository.owner}</p>
        </div>
        <MatchBadge label={recommendation.match_label} />
      </header>
      {repository.description && <p className="text-sm">{repository.description}</p>}
      <TechnologyChips technologies={recommendation.technologies} limit={MAX_TECHNOLOGIES} />
      {reasons.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm" aria-label="Why it matches">
          {reasons.slice(0, MAX_REASONS).map((reason) => (
            <li key={reason.type}>{reason.text}</li>
          ))}
        </ul>
      )}
      <footer className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {activity_label && <span>{ACTIVITY_TEXT[activity_label]}</span>}
        {setup && <span>{setup}</span>}
        {recommendation.relevant_issue_count > 0 && (
          <Link
            to={`/app/recommendations/${recommendation.id}#relevant-issues`}
            className="text-foreground rounded-full border px-2 py-0.5 hover:underline"
          >
            {recommendation.relevant_issue_count === 1
              ? '1 relevant issue'
              : `${recommendation.relevant_issue_count} relevant issues`}
          </Link>
        )}
        <ExternalLink
          href={repository.html_url}
          className="text-foreground underline-offset-2 hover:underline"
          onOpen={() => recordFeedback(recommendation.id, 'opened_repository')}
        >
          Open on GitHub
        </ExternalLink>
        <span className="ml-auto flex gap-2">
          <SaveButton recommendation={recommendation} />
          <DismissButton recommendation={recommendation} onDismissed={onDismissed} />
        </span>
      </footer>
    </article>
  )
}
