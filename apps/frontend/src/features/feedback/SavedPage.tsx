import { Link } from 'react-router'

import type { DismissedRepository, SavedRepository } from '@/api/types'
import { ExternalLink } from '@/components/ExternalLink'
import { Button } from '@/components/ui/button'
import { ACTIVITY_TEXT } from '@/features/recommendations/messages'
import { MatchBadge } from '@/features/recommendations/RecommendationCard'
import { formatDate } from '@/lib/format'

import { useDismissed, useRestore, useSaved, useUnsaveRepository } from './api'
import { DISMISS_REASON_TEXT } from './messages'

function SavedEntry({ entry }: { entry: SavedRepository }) {
  const unsave = useUnsaveRepository()
  const { repository, recommendation } = entry
  const headingId = `saved-${entry.repository_id}`
  return (
    <article aria-labelledby={headingId} className="space-y-2 rounded-md border p-4">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 id={headingId} className="font-medium break-words">
            {recommendation ? (
              <Link to={`/app/recommendations/${recommendation.id}`} className="hover:underline">
                {repository.full_name}
              </Link>
            ) : (
              repository.full_name
            )}
          </h3>
          <p className="text-muted-foreground text-xs">Saved {formatDate(entry.saved_at)}</p>
        </div>
        {recommendation && <MatchBadge label={recommendation.match_label} />}
      </header>
      {repository.description && <p className="text-sm">{repository.description}</p>}
      {recommendation ? (
        recommendation.reasons.length > 0 && (
          <p className="text-muted-foreground text-sm">{recommendation.reasons[0]!.text}</p>
        )
      ) : (
        <p className="text-muted-foreground text-sm">
          No longer recommended: it no longer fits your latest profile or the project changed.
        </p>
      )}
      <footer className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {entry.activity_label && <span>{ACTIVITY_TEXT[entry.activity_label]}</span>}
        <ExternalLink
          href={repository.html_url}
          className="text-foreground underline-offset-2 hover:underline"
        >
          Open on GitHub
        </ExternalLink>
        <Button
          variant="outline"
          size="sm"
          className="ml-auto"
          disabled={unsave.isPending}
          onClick={() => unsave.mutate(entry.repository_id)}
        >
          Remove
        </Button>
      </footer>
    </article>
  )
}

function HiddenEntry({ entry }: { entry: DismissedRepository }) {
  const restore = useRestore()
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 border-b py-2 text-sm last:border-0">
      <span className="min-w-0 break-words">
        {entry.repository.full_name}
        {entry.reason && (
          <span className="text-muted-foreground block text-xs">
            Reason: {DISMISS_REASON_TEXT[entry.reason]}
          </span>
        )}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={restore.isPending}
        onClick={() => restore.mutate(entry.repository_id)}
      >
        Restore
      </Button>
    </li>
  )
}

/** Loads the next page of a list; shown only while there is one. */
function ShowMore({
  list,
}: {
  list: ReturnType<typeof useSaved> | ReturnType<typeof useDismissed>
}) {
  if (!list.hasNextPage) return null
  return (
    <Button
      variant="outline"
      size="sm"
      disabled={list.isFetchingNextPage}
      onClick={() => void list.fetchNextPage()}
    >
      Show more
    </Button>
  )
}

/** Saved projects (kept even when no longer recommended) and hidden projects. */
export function SavedPage() {
  const saved = useSaved()
  const dismissed = useDismissed()
  const savedEntries = saved.data?.pages.flatMap((page) => page.results) ?? []
  const hiddenEntries = dismissed.data?.pages.flatMap((page) => page.results) ?? []

  return (
    <>
      <Link to="/app" className="text-muted-foreground text-sm hover:underline">
        ← Back to recommendations
      </Link>

      <section className="space-y-3" aria-labelledby="saved-heading">
        <h1 id="saved-heading" className="text-2xl font-semibold">
          Saved projects
        </h1>
        {saved.isPending ? (
          <p className="text-muted-foreground text-sm">Loading…</p>
        ) : !saved.data ? (
          <p role="alert">Could not load your saved projects. Please refresh the page.</p>
        ) : savedEntries.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            Nothing saved yet. Use Save on a recommendation to keep it here.
          </p>
        ) : (
          <>
            <div className="space-y-3">
              {savedEntries.map((entry) => (
                <SavedEntry key={entry.repository_id} entry={entry} />
              ))}
            </div>
            <ShowMore list={saved} />
          </>
        )}
      </section>

      <section className="space-y-3" aria-labelledby="hidden-heading">
        <h2 id="hidden-heading" className="font-medium">
          Hidden projects
        </h2>
        <p className="text-muted-foreground text-xs">
          Projects you dismissed are never recommended again. Restore one to let it come back.
        </p>
        {dismissed.isPending ? (
          <p className="text-muted-foreground text-sm">Loading…</p>
        ) : !dismissed.data ? (
          <p role="alert">Could not load your hidden projects. Please refresh the page.</p>
        ) : hiddenEntries.length === 0 ? (
          <p className="text-muted-foreground text-sm">No hidden projects.</p>
        ) : (
          <>
            <ul aria-label="Hidden projects">
              {hiddenEntries.map((entry) => (
                <HiddenEntry key={entry.repository_id} entry={entry} />
              ))}
            </ul>
            <ShowMore list={dismissed} />
          </>
        )}
      </section>
    </>
  )
}
