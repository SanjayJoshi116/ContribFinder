import { useEffect, useRef } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'

/** A page that cannot show what was asked for: what happened as the page heading, an optional
 * "Try again", and the way back. The heading takes keyboard focus when it appears, so a page
 * that turns into a dead end during a visit does not drop focus to the body (CMP-8). */
export function DeadEnd({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    heading.current?.focus()
  }, [])

  return (
    <div className="space-y-3">
      <h1 ref={heading} tabIndex={-1} className="text-lg font-medium outline-none">
        {message}
      </h1>
      <div className="flex flex-wrap items-center gap-4">
        {onRetry && (
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        )}
        <Link to="/app" className="text-sm underline">
          Back to your dashboard
        </Link>
      </div>
    </div>
  )
}
