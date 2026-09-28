import { Navigate, Outlet } from 'react-router'

import { useMe } from './api'

export function RequireAuth() {
  const me = useMe()

  if (me.isPending) {
    return (
      <div className="text-muted-foreground flex min-h-svh items-center justify-center">
        Loading…
      </div>
    )
  }
  if (me.isError) {
    if (me.error.status === 401) return <Navigate to="/" replace />
    return (
      <div role="alert" className="flex min-h-svh items-center justify-center p-4 text-center">
        Something went wrong loading your account. Please refresh the page.
      </div>
    )
  }
  return <Outlet />
}
