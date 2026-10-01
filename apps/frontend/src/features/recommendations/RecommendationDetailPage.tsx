import { useEffect, useRef } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import type { RecommendationDetail } from '@/api/types'
import { recordFeedback } from '@/features/feedback/api'
import { DismissButton, SaveButton } from '@/features/feedback/RecommendationActions'

import { useRecommendation } from './api'
import { ACTIVITY_TEXT, SIZE_TEXT } from './messages'
import { MatchBadge, TechnologyChips } from './RecommendationCard'

const date = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const UNAVAILABLE = 'Not available'

const OPENNESS_LABELS: [keyof RecommendationDetail['openness'], string][] = [
  ['contributing', 'Contributing guide'],
  ['code_of_conduct', 'Code of conduct'],
  ['issue_templates', 'Issue templates'],
  ['pull_request_template', 'Pull request template'],
  ['good_first_issue', '"good first issue" label'],
  ['help_wanted', '"help wanted" label'],
]

function yesNo(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return UNAVAILABLE
  return value ? 'Yes' : 'No'
}

function count(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return UNAVAILABLE
  return `${value} ${unit}${value === 1 ? '' : 's'}`
}

function Fact({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b py-1 text-sm last:border-0">
      <dt className="text-muted-foreground">{term}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function ActivityFacts({ signals }: { signals: RecommendationDetail['activity_signals'] }) {
  if (!signals) return <p className="text-muted-foreground text-sm">{UNAVAILABLE}</p>
  return (
    <dl>
      <Fact
        term="Last push"
        value={
          signals.days_since_push === null || signals.days_since_push === undefined
            ? UNAVAILABLE
            : signals.days_since_push === 0
              ? 'Today'
              : `${count(signals.days_since_push, 'day')} ago`
        }
      />
      <Fact term="Commits in 90 days" value={count(signals.commits_90d, 'commit')} />
      <Fact
        term="Merged pull requests in 90 days"
        value={count(signals.prs_merged_90d, 'pull request')}
      />
      <Fact term="Contributors" value={count(signals.contributors, 'contributor')} />
      <Fact
        term="Latest release"
        value={
          signals.latest_release_at ? date.format(new Date(signals.latest_release_at)) : 'None'
        }
      />
      <Fact term="Open issues and pull requests" value={String(signals.open_issues)} />
    </dl>
  )
}

function LanguageBar({ languages }: { languages: RecommendationDetail['languages'] }) {
  if (languages.length === 0) return <p className="text-muted-foreground text-sm">{UNAVAILABLE}</p>
  return (
    <ul className="space-y-1" aria-label="Languages by amount of code">
      {languages.slice(0, 6).map((lang) => (
        <li key={lang.language} className="flex items-center gap-2 text-sm">
          <span className="w-28 shrink-0 truncate">{lang.language}</span>
          <span className="bg-secondary h-2 flex-1 rounded" aria-hidden="true">
            <span
              className="bg-primary block h-2 rounded"
              style={{ width: `${Math.max(2, Math.round(lang.share * 100))}%` }}
            />
          </span>
        </li>
      ))}
    </ul>
  )
}

/** One recommendation: GitHub's facts kept visibly apart from ContribFinder's analysis. */
export function RecommendationDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const recommendation = useRecommendation(Number(id))
  const loadedId = recommendation.data?.id
  const viewed = useRef<number | null>(null)

  // One view per page visit (the backend also de-duplicates within a window).
  useEffect(() => {
    if (loadedId !== undefined && viewed.current !== loadedId) {
      viewed.current = loadedId
      recordFeedback(loadedId, 'viewed')
    }
  }, [loadedId])

  if (recommendation.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (recommendation.isError) {
    return (
      <div className="space-y-2">
        <p role="alert">
          {recommendation.error.status === 404
            ? 'This recommendation no longer exists. Recommendations change as your profile and projects are refreshed.'
            : 'Could not load this recommendation. Please refresh the page.'}
        </p>
        <Link to="/app" className="text-sm underline">
          Back to your dashboard
        </Link>
      </div>
    )
  }

  const rec = recommendation.data
  const { repository } = rec
  return (
    <>
      <Link to="/app" className="text-muted-foreground text-sm hover:underline">
        ← Back to recommendations
      </Link>

      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold break-words">{repository.full_name}</h1>
          <MatchBadge label={rec.match_label} />
        </div>
        {repository.description && (
          <p className="text-muted-foreground">{repository.description}</p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <a
            href={repository.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm underline-offset-2 hover:underline"
            onClick={() => recordFeedback(rec.id, 'opened_repository')}
          >
            Open on GitHub
          </a>
          <SaveButton recommendation={rec} />
          <DismissButton
            recommendation={rec}
            onDismissed={(project) => navigate('/app', { state: { dismissed: project } })}
          />
        </div>
      </header>

      <section className="space-y-4 rounded-md border p-4" aria-labelledby="analysis-heading">
        <h2 id="analysis-heading" className="font-medium">
          ContribFinder analysis
        </h2>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Why it matches</h3>
          {rec.reasons.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {rec.reasons.map((reason) => (
                <li key={reason.type}>{reason.text}</li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">{UNAVAILABLE}</p>
          )}
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Technologies</h3>
          <p className="text-muted-foreground text-xs">Highlighted ones are in your profile.</p>
          <TechnologyChips technologies={rec.technologies} />
        </div>
        <p className="text-muted-foreground text-sm">
          {rec.activity_label ? ACTIVITY_TEXT[rec.activity_label] : 'Activity unknown'} ·{' '}
          {SIZE_TEXT[rec.size]}
        </p>
      </section>

      <section className="space-y-4 rounded-md border p-4" aria-labelledby="github-heading">
        <h2 id="github-heading" className="font-medium">
          From GitHub
        </h2>
        <dl>
          <Fact term="Owner" value={repository.owner} />
          <Fact term="Stars" value={String(repository.stars)} />
          <Fact term="License" value={repository.license || UNAVAILABLE} />
        </dl>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Topics</h3>
          {repository.topics.length > 0 ? (
            <ul className="flex flex-wrap gap-1.5">
              {repository.topics.map((topic) => (
                <li key={topic} className="rounded border px-1.5 py-0.5 text-xs">
                  {topic}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">No topics</p>
          )}
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Languages</h3>
          <LanguageBar languages={rec.languages} />
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Activity</h3>
          <ActivityFacts signals={rec.activity_signals} />
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Contribution guidelines</h3>
          <dl>
            {OPENNESS_LABELS.map(([key, label]) => (
              <Fact key={key} term={label} value={yesNo(rec.openness[key])} />
            ))}
          </dl>
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">README</h3>
          {rec.readme_excerpt ? (
            <p className="text-sm whitespace-pre-line">{rec.readme_excerpt}</p>
          ) : (
            <p className="text-muted-foreground text-sm">No README available.</p>
          )}
        </div>
      </section>
    </>
  )
}
