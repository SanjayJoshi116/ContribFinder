/** Where the detail page returns to: the list page and filters it was opened from. Card links
 * pass the list's search string as navigation state; anything else falls back to `/app`. */
export interface FromList {
  from: string
}

export function listState(search: string): FromList {
  return { from: search }
}

/** `/app` plus the search string the detail page was opened from, when it is one. */
export function listPath(state: unknown): string {
  const from = (state as Partial<FromList> | null)?.from
  return typeof from === 'string' && from.startsWith('?') ? `/app${from}` : '/app'
}
