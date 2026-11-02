import { Navigate, Outlet } from 'react-router'

import { useMe } from './api'

export function RequireAuth() {
  const me = useMe()

  // A known identity keeps the pages: a failed refresh is not a sign-out, and a 401 on it ends
  // the session through the query client (the session-ended notice).
  if (me.data) return <Outlet />
  if (me.isPending) {
    return (
      <div className="text-muted-foreground flex min-h-svh items-center justify-center">
        Loading…
      </div>
    )
  }
  if (me.error.status === 401) return <Navigate to="/" replace />
  return (
    <div role="alert" className="flex min-h-svh items-center justify-center p-4 text-center">
      Something went wrong loading your account. Please refresh the page.
    </div>
  )
}
