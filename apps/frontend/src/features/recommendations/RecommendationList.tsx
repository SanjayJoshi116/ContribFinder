import { useIsMutating } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'

import { Loading } from '@/components/Loading'
import { Button } from '@/components/ui/button'
import { dismissMutationKey } from '@/features/feedback/api'
import { type DismissedProject, DismissUndo } from '@/features/feedback/RecommendationActions'
import { cn } from '@/lib/utils'

import {
  FILTER_KEYS,
  type FilterKey,
  type RecommendationFilters,
  useRecommendationStatus,
  useRecommendations,
} from './api'
import {
  ACTIVITY_OPTIONS,
  CONTRIBUTION_TYPE_OPTIONS,
  DIFFICULTY_OPTIONS,
  FRAMEWORK_OPTIONS,
  LANGUAGE_OPTIONS,
  MATCH_OPTIONS,
  type Option,
  SIZE_OPTIONS,
  emptyReason,
  isGenerating,
} from './messages'
import { listState } from './navigation'
import { RecommendationCard } from './RecommendationCard'

const FILTERS: { key: FilterKey; label: string; options: Option[] }[] = [
  { key: 'language', label: 'Language', options: LANGUAGE_OPTIONS },
  { key: 'framework', label: 'Framework', options: FRAMEWORK_OPTIONS },
  { key: 'activity', label: 'Activity', options: ACTIVITY_OPTIONS },
  { key: 'size', label: 'Size', options: SIZE_OPTIONS },
  { key: 'match', label: 'Match', options: MATCH_OPTIONS },
  { key: 'difficulty', label: 'Issue difficulty', options: DIFFICULTY_OPTIONS },
  { key: 'contribution_type', label: 'Contribution type', options: CONTRIBUTION_TYPE_OPTIONS },
]

/** One API page (the backend's page size). */
const FILTERS_MIN_COUNT = 20

function readFilters(params: URLSearchParams): RecommendationFilters {
  const filters: RecommendationFilters = {}
  for (const key of FILTER_KEYS) {
    const value = params.get(key)
    if (value) filters[key] = value
  }
  const page = Number(params.get('page'))
  if (Number.isInteger(page) && page > 1) filters.page = page
  return filters
}

/** Recommended projects with URL-backed filters: a reload or shared link keeps them. */
export function RecommendationList() {
  const [params, setParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  // A dismissal from the detail page arrives as navigation state. It is taken once: the state
  // is cleared at once, so a reload or Back does not offer the undo again.
  const arrived = (location.state as { dismissed?: DismissedProject } | null)?.dismissed
  const [dismissed, setDismissed] = useState<DismissedProject | null>(() => arrived ?? null)
  useEffect(() => {
    if (arrived) void navigate(location, { replace: true, state: null })
  }, [arrived, location, navigate])
  const closeUndo = () => setDismissed(null)
  const filters = readFilters(params)
  const filtered = FILTER_KEYS.some((key) => filters[key])
  const status = useRecommendationStatus()
  const list = useRecommendations(filters)
  const generating = isGenerating(status.data)
  // Filters earn their place only when there is more than one page to narrow down; an active
  // filter (e.g. from a shared link) always stays visible so it can be cleared.
  const showFilters = filtered || (status.data?.count ?? 0) > FILTERS_MIN_COUNT

  const update = (key: FilterKey | 'page', value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }
  const clearFilters = () => {
    const next = new URLSearchParams(params)
    for (const key of [...FILTER_KEYS, 'page']) next.delete(key)
    setParams(next, { replace: true })
  }
  const clearButton = (
    <Button type="button" variant="ghost" size="sm" onClick={clearFilters}>
      Clear filters
    </Button>
  )

  const page = filters.page ?? 1
  // Detail links return here: this page and these filters.
  const back = listState(location.search)
  const results = list.data?.results ?? []
  // A dismissal empties its page at once; only once it is confirmed is the page really empty.
  const dismissing = useIsMutating({ mutationKey: dismissMutationKey }) > 0
  // The previous page's or filter's results, kept on screen until the new ones arrive.
  const stale = list.isPlaceholderData
  // An empty page shows "Loading…" while a dismissal is in flight or old results are shown,
  // not during every background refetch (focus, data versions, generation polling).
  const settling = dismissing || stale

  // A page that no longer exists (dismissals or a regeneration shrank the list, an old link)
  // moves to one that does: past the end → page 1 (the 404 does not say which page is last);
  // emptied by confirmed dismissals with earlier pages → the previous page. Moving off an
  // emptied page also waits for a refetch under way: after a dismissal the list is refetched,
  // and that may still fill it.
  let recoverTo: number | null = null
  if (page > 1) {
    if (list.isError && list.error.status === 404) recoverTo = 1
    else if (
      list.isSuccess &&
      !settling &&
      !list.isFetching &&
      results.length === 0 &&
      list.data.previous
    )
      recoverTo = page - 1
  }
  useEffect(() => {
    if (recoverTo === null) return
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        if (recoverTo > 1) next.set('page', String(recoverTo))
        else next.delete('page')
        return next
      },
      { replace: true },
    )
  }, [recoverTo, setParams])

  return (
    <section className="space-y-4" aria-labelledby="recommendations-heading">
      <div className="space-y-1">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="recommendations-heading" className="font-medium">
            Recommended projects
          </h2>
          <Link to="/app/saved" className="text-sm underline-offset-2 hover:underline">
            Saved and hidden projects
          </Link>
        </div>
        <p className="text-muted-foreground text-xs">
          Ranked by how well each project fits your evidence. Labels summarize the fit; the reasons
          show what it is based on.
        </p>
      </div>

      {showFilters && (
        <form className="flex flex-wrap items-end gap-3" aria-label="Filter recommendations">
          {FILTERS.map(({ key, label, options }) => (
            <label key={key} className="flex flex-col gap-1 text-xs">
              {label}
              <select
                className="bg-background h-8 rounded-md border px-2 text-sm"
                value={filters[key] ?? ''}
                onChange={(event) => update(key, event.target.value)}
              >
                <option value="">Any</option>
                {options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
                {/* A value from a link that is not an option is still shown as selected. */}
                {filters[key] && !options.some((option) => option.value === filters[key]) && (
                  <option value={filters[key]}>{filters[key]}</option>
                )}
              </select>
            </label>
          ))}
          {filtered && clearButton}
        </form>
      )}

      {dismissed && (
        <DismissUndo key={dismissed.repositoryId} project={dismissed} onClose={closeUndo} />
      )}

      {generating && (
        <p role="status" className="text-muted-foreground text-sm">
          Preparing your recommendations…
        </p>
      )}

      {list.isPending || recoverTo !== null ? (
        <Loading />
      ) : !list.data ? (
        list.error?.code === 'validation_error' ? (
          <div className="flex flex-wrap items-center gap-2">
            <p role="alert" className="text-sm">
              These filters are not valid. Clear them and try again.
            </p>
            {clearButton}
          </div>
        ) : (
          <p role="alert" className="text-sm">
            Could not load recommendations. Please refresh the page.
          </p>
        )
      ) : results.length === 0 ? (
        generating ? null : settling ? (
          <Loading />
        ) : (
          <p className="text-muted-foreground text-sm">{emptyReason(status.data, filtered)}</p>
        )
      ) : (
        <>
          <div className={cn('space-y-3', stale && 'opacity-60')} aria-busy={stale}>
            {results.map((recommendation) => (
              <RecommendationCard
                key={recommendation.id}
                recommendation={recommendation}
                onDismissed={setDismissed}
                back={back}
              />
            ))}
          </div>
          {(list.data.previous || list.data.next) && (
            <nav className="flex items-center gap-3" aria-label="Recommendation pages">
              <Button
                variant="outline"
                size="sm"
                disabled={stale || !list.data.previous}
                onClick={() => update('page', page > 2 ? String(page - 1) : '')}
              >
                Previous
              </Button>
              <span className="text-muted-foreground text-xs">Page {page}</span>
              <Button
                variant="outline"
                size="sm"
                disabled={stale || !list.data.next}
                onClick={() => update('page', String(page + 1))}
              >
                Next
              </Button>
            </nav>
          )}
        </>
      )}
    </section>
  )
}
