import { Outlet, useNavigate } from 'react-router'

import { Button } from '@/components/ui/button'
import { useLogout, useMe } from '@/features/auth/api'

export function SignedInLayout() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const logout = useLogout()

  if (!me) return null

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
            disabled={logout.isPending}
            onClick={() =>
              logout.mutate(undefined, { onSuccess: () => navigate('/', { replace: true }) })
            }
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
        <Outlet />
      </main>
    </div>
  )
}
