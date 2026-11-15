import { useEffect, useRef } from 'react'
import { Outlet, useLocation } from 'react-router'

import { useDataVersions } from '@/app/dataVersions'
import { Button } from '@/components/ui/button'
import { useAccountActionPending, useLogout, useSignedInUser } from '@/features/auth/api'
import { PageVisit, useVisitOf } from '@/features/feedback/visit'

export function SignedInLayout() {
  const me = useSignedInUser()
  const logout = useLogout()
  const accountActionPending = useAccountActionPending()
  const { refetch: refetchVersions } = useDataVersions()
  const { pathname, search, hash } = useLocation()
  const route = pathname + search + hash
  const previousRoute = useRef(route)
  const visit = useVisitOf(route)

  // Every route change asks which derived data changed; the mount fetch covers the first one.
  // Compared with the previous route, so Back to the first page counts (ROUTE-1), and a
  // state-only navigation does not (ROUTE-7).
  useEffect(() => {
    if (route === previousRoute.current) return
    previousRoute.current = route
    void refetchVersions()
  }, [route, refetchVersions])

  return (
    <div className="min-h-svh">
      <header className="flex items-center justify-between gap-4 border-b px-4 py-3 sm:px-6">
        <span className="font-semibold">ContribFinder</span>
        <div className="flex items-center gap-3">
          {me.avatar_url && <img src={me.avatar_url} alt="" className="size-8 rounded-full" />}
          <span className="hidden text-sm sm:inline">{me.github_username}</span>
          <Button
            variant="outline"
            size="sm"
            disabled={accountActionPending}
            onClick={() => logout.mutate()}
          >
            Log out
          </Button>
        </div>
      </header>
      {logout.isError && (
        <p role="alert" className="text-destructive px-4 pt-3 text-sm sm:px-6">
          Logging out didn&apos;t work. Please try again.
        </p>
      )}
      <main className="mx-auto max-w-3xl space-y-8 px-4 py-10 sm:px-6">
        <PageVisit value={visit}>
          <Outlet context={me} />
        </PageVisit>
      </main>
    </div>
  )
}
