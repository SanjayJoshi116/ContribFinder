import { createContext, useContext, useState } from 'react'

/** The current page visit: a value that changes on every route change, Back included. A
 * failed action's inline text belongs to the visit it was started in, so it never follows the
 * item to another page or to a later visit of the same one. Without a provider (component
 * tests) every action shares one visit. */
export const PageVisit = createContext('')

export const usePageVisit = () => useContext(PageVisit)

/** A new visit value whenever ``route`` changes (adjusted during render, so the new page's
 * first render already sees it). */
export function useVisitOf(route: string): string {
  const [visit, setVisit] = useState({ route, count: 0 })
  if (visit.route !== route) {
    const next = { route, count: visit.count + 1 }
    setVisit(next)
    return String(next.count)
  }
  return String(visit.count)
}
