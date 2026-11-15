import { Link } from 'react-router'

import { Button } from '@/components/ui/button'

/** The root route's error screen: any render error lands here instead of the router's default
 * screen (CMP-1). It never shows the error's text, which could carry internals. */
export function RouteError() {
  return (
    <main className="flex min-h-svh items-center justify-center px-4">
      <section className="max-w-md space-y-4 text-center">
        <h1 className="text-2xl font-semibold">Something went wrong</h1>
        <p className="text-muted-foreground text-sm">
          This page could not be shown. Reload it, or go back to your dashboard.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Button type="button" onClick={() => window.location.reload()}>
            Reload
          </Button>
          <Link to="/app" className="text-sm underline">
            Back to your dashboard
          </Link>
        </div>
      </section>
    </main>
  )
}
