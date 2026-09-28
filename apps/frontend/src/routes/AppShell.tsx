import { useNavigate } from 'react-router'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { useDisconnectGitHub, useLogout, useMe } from '@/features/auth/api'

export function AppShell() {
  const { data: me } = useMe()
  const navigate = useNavigate()
  const logout = useLogout()
  const disconnect = useDisconnectGitHub()
  const busy = logout.isPending || disconnect.isPending

  const goHome = () => navigate('/', { replace: true })

  if (!me) return null
  const name = me.display_name || me.github_username || 'there'

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
            disabled={busy}
            onClick={() => logout.mutate(undefined, { onSuccess: goHome })}
          >
            Log out
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-8 px-4 py-10 sm:px-6">
        <section className="space-y-2">
          <h1 className="text-2xl font-semibold">Welcome, {name}</h1>
          <p className="text-muted-foreground">
            Signed in as <strong>@{me.github_username}</strong>. Profile analysis arrives in the
            next release.
          </p>
        </section>

        <section className="space-y-3 rounded-lg border p-4">
          <h2 className="font-medium">GitHub connection</h2>
          <p className="text-muted-foreground text-sm">
            Disconnecting revokes ContribFinder&apos;s access on GitHub, deletes the stored
            credential, and signs you out.
          </p>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm" disabled={busy}>
                Disconnect GitHub
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Disconnect GitHub?</AlertDialogTitle>
                <AlertDialogDescription>
                  We will ask GitHub to revoke ContribFinder&apos;s access, delete the stored GitHub
                  credential, and sign you out. You can reconnect later by signing in again.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => disconnect.mutate(undefined, { onSuccess: goHome })}
                >
                  Disconnect
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          {(logout.isError || disconnect.isError) && (
            <p role="alert" className="text-destructive text-sm">
              That didn&apos;t work. Please try again.
            </p>
          )}
        </section>
      </main>
    </div>
  )
}
