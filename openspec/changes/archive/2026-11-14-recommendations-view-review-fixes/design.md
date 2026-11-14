## Context

Findings and verdicts are in `Bug_Backlog.md` (batch 65, REC-1…REC-10). Relevant facts:

- Filter selects are controlled (`value={filters[key] ?? ''}`). A value that matches no option
  shows as the first option ("Any"), and choosing it fires no change. The backend accepts any
  Linguist language name, any catalog skill slug and `size=unknown`; the options list 7, 6 and
  3 of those. Invalid values return `validation_error`.
- `useDismiss` removes the card from every cached list page optimistically. On settle it
  invalidates only the saved and dismissed lists. The recovery in `RecommendationList` runs only
  when `page > 1`.
- The undo state comes from `location.state.dismissed`, read in a `useState` initializer, and
  is cleared by `closeUndo` with a `replace` navigation. Browsers keep history state across a
  reload and on Back.
- `useRecommendations` uses `placeholderData: (previous) => previous`. The page label and
  `update()` read the URL, while `next`/`previous` come from the placeholder data.
- Detail page: `<Link to="/app">` and `navigate('/app', { state: { dismissed } })`.
- `schema.d.ts` has `ActivityLabelEnum` and `SizeEnum`. `types.ts` exports neither.

## Goals / Non-Goals

**Goals:** the behavior in the spec deltas; no backend change; existing tests and e2e stay green.

**Non-Goals:** a combobox for every Linguist language or catalog slug; remembering list scroll
position; a global store for list state.

## Decisions

### D1. Unknown filter values and clearing (REC-1)

`FilterSelect` renders the current value as an extra `<option>` when it is not in `options`
(label = the raw value). A "Clear filters" button (`variant="ghost"`) appears in the filter form
when `filtered`. The invalid-filter alert gets the same button. Clearing removes every
`FILTER_KEYS` key and `page` with `replace`. Rejected alternative: dropping unknown values from
the URL on load. That would silently change a shared link's meaning, and some of those values
are valid on the backend.

### D2. Refetch after a dismissal (REC-2, REC-3)

`useDismiss.onSettled` also calls `invalidateQueries({ queryKey: recommendationListKey })`, which
refetches only the active page. With the existing recovery, an emptied page > 1 still moves to
the previous page first (recovery runs as soon as `dismissing` is false). Page 1 refetches and
shows the next recommendations. In the empty branch, `dismissing && results.length === 0`
renders "Loading…". Rejected alternative: a page-1 special case that refetches only when emptied.
It keeps two mechanisms, and the cards on a non-empty page would drift from the server's order.

### D3. One-shot undo state (REC-4)

On mount, if `location.state?.dismissed` is set, keep it in component state and immediately
`navigate(location, { replace: true, state: null })` in an effect. `closeUndo` then only clears
component state. The 10-second window still runs from the dismissal (`DismissUndo` unchanged).

### D4. Placeholder results (REC-5)

`const stale = list.isPlaceholderData`. The results container gets `aria-busy={stale}` and
`opacity-60`. Previous/Next get `disabled={stale || ...}`. The empty branch shows "Loading…" when
`stale` (the placeholder may be an old empty result).

### D5. Return to the list's place (REC-6)

Card links (title and relevant-issue count) pass `state={{ from: location.search }}`.
`RecommendationDetailPage` reads `from` from `location.state` and uses it only when it is a
string starting with `?`, else `''`. It builds `/app${from}` for the Back link and for the
after-dismiss `navigate` (state `{ dismissed }`). Other entry points (saved list, issue page,
direct link) fall back to `/app`. Rejected alternative: storing the last list URL in Zustand.
It survives into unrelated visits, and history state already scopes it to the navigation.

### D6. Text cleanups (REC-7…REC-10)

- `LanguageBar` row: `<span className="w-16 text-right tabular-nums">{shareText(lang.share)}</span>`,
  where `shareText` returns `under 1%` below 0.005 and `Math.round(share * 100)%` otherwise. The
  bar stays `aria-hidden`.
- `types.ts`: `export type ActivityLabel = components['schemas']['ActivityLabelEnum']` and
  `RepositorySize = components['schemas']['SizeEnum']`. The maps are `Record<ActivityLabel, string>`
  and `Record<RepositorySize, string>`.
- `SIZE_OPTIONS` comes from `Object.entries(SIZE_TEXT)`, so its labels read "Small project" …
  "Size unknown".
- `difficultyText`: `difficulty === 'unknown' ? DIFFICULTY_TEXT.unknown : ...`.

## Risks / Trade-offs

- D2 refetches the current page after every dismissal, which is one request. Cards from the next
  page move up into the current page. That matches what a reload would show.
- D5 relies on history state. A detail page opened in a new tab has no `from` and goes back to
  `/app`, as today.
