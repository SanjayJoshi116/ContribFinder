import { Link, useParams } from 'react-router'

import { DeadEnd } from '@/components/DeadEnd'
import { recordFeedback } from '@/features/feedback/api'
import {
  CONTRIBUTION_TYPE_TEXT,
  NOT_ENOUGH_EVIDENCE,
  difficultyText,
} from '@/features/recommendations/messages'
import { MatchBadge } from '@/features/recommendations/RecommendationCard'
import { cn, positiveId } from '@/lib/utils'

import { useIssue } from './api'
import { contributionBasis, difficultyBasis } from './evidence'

const date = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })

function Fact({ term, value, note }: { term: string; value: string; note?: string | null }) {
  return (
    <div className="flex justify-between gap-4 border-b py-1 text-sm last:border-0">
      <dt className="text-muted-foreground">{term}</dt>
      <dd className="text-right">
        {value}
        {note && <span className="text-muted-foreground block text-xs">{note}</span>}
      </dd>
    </div>
  )
}

/** One relevant issue: GitHub's data kept visibly apart from ContribFinder's analysis. The
 * description is shown as plain text (React escapes it), never rendered as HTML. */
export function IssueDetailPage() {
  const { id: param } = useParams()
  const id = positiveId(param)
  // Disabled for an invalid id (0): nothing is requested.
  const issue = useIssue(id ?? 0)

  if (id === null) return <DeadEnd message="This link doesn't point to an issue." />
  if (issue.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (issue.isError) {
    return (
      <DeadEnd
        message={
          issue.error.status === 404
            ? 'This issue is no longer among your relevant issues. Issues change as projects are refreshed.'
            : 'Could not load this issue. Please refresh the page.'
        }
      />
    )
  }

  const { github, analysis } = issue.data
  const { recommendation } = analysis
  const basis = difficultyBasis(analysis)
  return (
    <>
      <Link
        to={`/app/recommendations/${recommendation.id}`}
        className="text-muted-foreground text-sm hover:underline"
      >
        ← Back to {recommendation.repository_full_name}
      </Link>

      <header className="space-y-2">
        <h1 className="text-2xl font-semibold break-words">{github.title}</h1>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-muted-foreground">
            {github.repository_full_name} #{github.number}
          </span>
          <MatchBadge label={recommendation.match_label} />
          <a
            href={github.url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline-offset-2 hover:underline"
            onClick={() =>
              recordFeedback(recommendation.id, 'opened_issue', { issue_id: issue.data.id })
            }
          >
            Open on GitHub
          </a>
        </div>
      </header>

      <section className="space-y-4 rounded-md border p-4" aria-labelledby="analysis-heading">
        <h2 id="analysis-heading" className="font-medium">
          ContribFinder analysis
        </h2>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Why it matches</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {analysis.reasons.map((reason) => (
              <li key={reason.type}>{reason.text}</li>
            ))}
          </ul>
        </div>
        <dl>
          <Fact
            term="Contribution type"
            value={CONTRIBUTION_TYPE_TEXT[analysis.contribution_type]}
            note={contributionBasis(analysis)}
          />
          <Fact
            term="Difficulty"
            value={difficultyText(analysis.difficulty)}
            note={basis.length > 0 ? `Based on: ${basis.join(', ')}` : null}
          />
        </dl>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Technologies mentioned</h3>
          {analysis.technologies.length > 0 ? (
            <>
              <p className="text-muted-foreground text-xs">Highlighted ones are in your profile.</p>
              <ul className="flex flex-wrap gap-1.5" aria-label="Technologies">
                {analysis.technologies.map((tech) => (
                  <li
                    key={tech.slug}
                    className={cn(
                      'rounded border px-1.5 py-0.5 text-xs',
                      tech.matched ? 'bg-secondary font-medium' : 'text-muted-foreground',
                    )}
                  >
                    {tech.name}
                    {tech.matched && <span className="sr-only"> (in your profile)</span>}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-muted-foreground text-sm">{NOT_ENOUGH_EVIDENCE}</p>
          )}
        </div>
      </section>

      <section className="space-y-4 rounded-md border p-4" aria-labelledby="github-heading">
        <h2 id="github-heading" className="font-medium">
          From GitHub
        </h2>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Labels</h3>
          {github.labels.length > 0 ? (
            <ul className="flex flex-wrap gap-1.5" aria-label="Labels">
              {github.labels.map((label) => (
                <li key={label} className="rounded border px-1.5 py-0.5 text-xs">
                  {label}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">No labels</p>
          )}
        </div>
        <dl>
          <Fact term="State" value={github.state === 'open' ? 'Open' : github.state} />
          <Fact term="Comments" value={String(github.comments)} />
          {github.created_at && (
            <Fact term="Opened" value={date.format(new Date(github.created_at))} />
          )}
          {github.updated_at && (
            <Fact term="Last updated" value={date.format(new Date(github.updated_at))} />
          )}
        </dl>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Description</h3>
          {github.body ? (
            <pre
              data-testid="issue-body"
              className="bg-muted max-h-[32rem] overflow-auto rounded p-3 font-sans text-sm whitespace-pre-wrap"
            >
              {github.body}
            </pre>
          ) : (
            <p className="text-muted-foreground text-sm">No description.</p>
          )}
        </div>
      </section>
    </>
  )
}
