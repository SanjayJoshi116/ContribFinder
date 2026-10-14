import { useCallback, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'

import { Button } from '@/components/ui/button'
import { type DismissedProject, DismissUndo } from '@/features/feedback/RecommendationActions'

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
  // A dismissal from the detail page arrives as navigation state.
  const [dismissed, setDismissed] = useState<DismissedProject | null>(
    () => (location.state as { dismissed?: DismissedProject } | null)?.dismissed ?? null,
  )
  const closeUndo = useCallback(() => {
    setDismissed(null)
    if (location.state) void navigate(location, { replace: true, state: null })
  }, [location, navigate])
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

  const page = filters.page ?? 1
  const results = list.data?.results ?? []

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
        <form className="flex flex-wrap gap-3" aria-label="Filter recommendations">
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
              </select>
            </label>
          ))}
        </form>
      )}

      {dismissed && <DismissUndo project={dismissed} onClose={closeUndo} />}

      {generating && (
        <p role="status" className="text-muted-foreground text-sm">
          Preparing your recommendations…
        </p>
      )}

      {list.isPending ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : list.isError ? (
        <p role="alert" className="text-sm">
          {list.error.code === 'validation_error'
            ? 'These filters are not valid. Clear them and try again.'
            : 'Could not load recommendations. Please refresh the page.'}
        </p>
      ) : results.length === 0 ? (
        !generating && (
          <p className="text-muted-foreground text-sm">{emptyReason(status.data, filtered)}</p>
        )
      ) : (
        <>
          <div className="space-y-3">
            {results.map((recommendation) => (
              <RecommendationCard
                key={recommendation.id}
                recommendation={recommendation}
                onDismissed={setDismissed}
              />
            ))}
          </div>
          {(list.data.previous || list.data.next) && (
            <nav className="flex items-center gap-3" aria-label="Recommendation pages">
              <Button
                variant="outline"
                size="sm"
                disabled={!list.data.previous}
                onClick={() => update('page', page > 2 ? String(page - 1) : '')}
              >
                Previous
              </Button>
              <span className="text-muted-foreground text-xs">Page {page}</span>
              <Button
                variant="outline"
                size="sm"
                disabled={!list.data.next}
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
