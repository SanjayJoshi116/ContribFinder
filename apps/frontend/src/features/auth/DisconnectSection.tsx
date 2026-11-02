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

import { useAccountActionPending, useDisconnectGitHub } from './api'

export function DisconnectSection() {
  const disconnect = useDisconnectGitHub()
  const busy = useAccountActionPending()

  return (
    <section className="space-y-3 rounded-lg border p-4">
      <h2 className="font-medium">GitHub connection</h2>
      <p className="text-muted-foreground text-sm">
        Disconnecting revokes ContribFinder&apos;s access on GitHub, deletes the stored credential,
        stops any sync in progress, deletes your GitHub data from ContribFinder, and signs you out.
        Your account stays, so you can sign in again and start over.
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
              credential, stop any sync in progress, delete your GitHub data (profile, skills,
              recommendations, saved and hidden projects), and sign you out. Signing in again syncs
              your data from scratch.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => disconnect.mutate()}>Disconnect</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {disconnect.isError && (
        <p role="alert" className="text-destructive text-sm">
          That didn&apos;t work. Please try again.
        </p>
      )}
    </section>
  )
}
