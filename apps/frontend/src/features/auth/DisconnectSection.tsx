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

import { useDisconnectGitHub } from './api'

export function DisconnectSection() {
  const navigate = useNavigate()
  const disconnect = useDisconnectGitHub()

  return (
    <section className="space-y-3 rounded-lg border p-4">
      <h2 className="font-medium">GitHub connection</h2>
      <p className="text-muted-foreground text-sm">
        Disconnecting revokes ContribFinder&apos;s access on GitHub, deletes the stored credential,
        stops any sync in progress, and signs you out. Your synced public profile data stays in
        ContribFinder for now; deleting it will be available in a later release.
      </p>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button variant="destructive" size="sm" disabled={disconnect.isPending}>
            Disconnect GitHub
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Disconnect GitHub?</AlertDialogTitle>
            <AlertDialogDescription>
              We will ask GitHub to revoke ContribFinder&apos;s access, delete the stored GitHub
              credential, stop any sync in progress, and sign you out. You can reconnect later by
              signing in again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                disconnect.mutate(undefined, {
                  onSuccess: () => navigate('/', { replace: true }),
                })
              }
            >
              Disconnect
            </AlertDialogAction>
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
