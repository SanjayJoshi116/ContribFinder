import { Fragment, type ReactNode } from 'react'
import { useParams } from 'react-router'

import { DeadEnd } from '@/components/DeadEnd'

/** A route `:id` as a positive integer, or null for anything else ("abc", "0", "1.5", "0x1f",
 * "1e2", " 7"). */
function positiveId(param: string | undefined): number | null {
  if (!param || !/^[1-9]\d*$/.test(param)) return null
  const id = Number(param)
  return Number.isSafeInteger(id) ? id : null
}

/** A detail route's `:id`, validated once: an invalid id gets the dead end with `invalid` and
 * no request; a valid one renders the page with a plain positive number, remounted per id. */
export function RouteId({
  invalid,
  children,
}: {
  invalid: string
  children: (id: number) => ReactNode
}) {
  const id = positiveId(useParams().id)
  if (id === null) return <DeadEnd message={invalid} />
  return <Fragment key={id}>{children(id)}</Fragment>
}
