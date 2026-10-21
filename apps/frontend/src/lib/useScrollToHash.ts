import { useEffect, useRef } from 'react'
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

/** Scrolls to the element named by the URL hash once `ready` (its content has loaded) and
 * moves keyboard focus to it; client-side navigation does neither by itself. Runs once per
 * navigation, so later re-renders leave the scroll position alone. The target needs
 * `tabIndex={-1}` to take focus. */
export function useScrollToHash(ready: boolean): void {
  const { hash, key } = useLocation()
  const done = useRef<string | null>(null)

  useEffect(() => {
    if (!ready || !hash || done.current === key) return
    const target = document.getElementById(decodeHash(hash))
    if (!target) return
    done.current = key
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    target.scrollIntoView({ block: 'start', behavior: reduceMotion ? 'auto' : 'smooth' })
    target.focus({ preventScroll: true })
  }, [ready, hash, key])
}
