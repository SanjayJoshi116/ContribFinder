import { useQueryClient } from '@tanstack/react-query'
import { LogIn } from 'lucide-react'
import { useEffect } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router'

import { clearSignedInData } from '@/app/session'
import { Loading } from '@/components/Loading'
import { Button } from '@/components/ui/button'
import { GITHUB_SIGN_IN_URL, useMe } from '@/features/auth/api'
import { authErrorMessage } from '@/features/auth/authErrors'

export function LandingPage() {
  const [params] = useSearchParams()
  const queryClient = useQueryClient()
  const me = useMe()
  const code = params.get('auth_error')
  const error = authErrorMessage(code)

  // An ended session leaves the previous user's data cached; the signed-in pages are
  // unmounted by now, so nothing refetches it.
  useEffect(() => {
    if (code === 'session_ended') clearSignedInData(queryClient)
  }, [code, queryClient])

  if (me.isSuccess) return <Navigate to="/app" replace />
  // A signed-in user must not see the sign-in button while the identity loads (ROUTE-10); the
  // same loading text as RequireAuth, so a slow or retried answer is not a blank page (CR-6).
  if (me.isPending) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Loading />
      </div>
    )
  }

  return (
    <main className="flex min-h-svh items-center justify-center px-4">
      <section className="w-full max-w-lg space-y-6 text-center">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Find Your Next OSS Contribution
        </h1>
        <p className="text-muted-foreground">
          Analyze your GitHub profile and discover repositories where you can contribute.
        </p>
        {error && (
          <p
            role="alert"
            className="border-destructive/40 text-destructive rounded-md border px-4 py-3 text-sm"
          >
            {error}
          </p>
        )}
        <Button asChild size="lg">
          {/* Full-page navigation: the OAuth flow is a server redirect, not an XHR. */}
          <a href={GITHUB_SIGN_IN_URL}>
            <LogIn aria-hidden="true" />
            Continue with GitHub
          </a>
        </Button>
        <p className="text-muted-foreground text-xs">
          We only read public GitHub data. You can disconnect and delete your data at any time.{' '}
          <Link to="/privacy" className="underline-offset-2 hover:underline">
            What we store
          </Link>
        </p>
      </section>
    </main>
  )
}
