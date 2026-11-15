import { useEffect } from 'react'
import { useLocation } from 'react-router'

/** The hash as an element id; a malformed escape (`#%E0`) is used as written. */
function decodeHash(hash: string): string {
  const id = hash.slice(1)
  try {
    return decodeURIComponent(id)
  } catch {
    return id
  }
}

/** History entries (location keys) already scrolled to in this page session. Module-level, so
 * Back to an entry whose page remounts does not scroll or focus again; a reload starts a new
 * module and scrolls (CMP-3). */
const handled = new Set<string>()

/** Forgets the handled entries. Tests only: every test's memory router starts at key "default". */
export function forgetScrolledEntries(): void {
  handled.clear()
}

/** Scrolls to the element named by the URL hash once `ready` (its content has loaded) and
 * moves keyboard focus to it; client-side navigation does neither by itself. Runs once per
 * history entry, so later re-renders and returns through Back leave the scroll position alone. The target needs
 * `tabIndex={-1}` to take focus. */
export function useScrollToHash(ready: boolean): void {
  const { hash, key } = useLocation()
  useEffect(() => {
    if (!ready || !hash || handled.has(key)) return
    const target = document.getElementById(decodeHash(hash))
    if (!target) return
    handled.add(key)
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    target.scrollIntoView({ block: 'start', behavior: reduceMotion ? 'auto' : 'smooth' })
    target.focus({ preventScroll: true })
  }, [ready, hash, key])
}
