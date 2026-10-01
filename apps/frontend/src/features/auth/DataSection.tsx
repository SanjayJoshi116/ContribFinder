import { Link, useNavigate } from 'react-router'

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

import { useDeleteAccount, useDeleteGitHubData } from './api'

const GITHUB_DATA =
  'your synced GitHub profile and profile README, your repository list, your developer profile ' +
  'with skills, interests and evidence, your candidate projects, recommendations, saved and ' +
  'hidden projects, feedback and sync history'

function ConfirmDelete({
  trigger,
  title,
  description,
  confirm,
  disabled,
  onConfirm,
}: {
  trigger: string
  title: string
  description: string
  confirm: string
  disabled: boolean
  onConfirm: () => void
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="destructive" size="sm" disabled={disabled}>
          {trigger}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>{confirm}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

/** "Your data": what is stored and how to delete it (FR-DATA-003). */
export function DataSection() {
  const navigate = useNavigate()
  const deleteData = useDeleteGitHubData()
  const deleteAccount = useDeleteAccount()
  const busy = deleteData.isPending || deleteAccount.isPending

  return (
    <section className="space-y-3 rounded-lg border p-4" aria-labelledby="your-data-heading">
      <h2 id="your-data-heading" className="font-medium">
        Your data
      </h2>
      <p className="text-muted-foreground text-sm">
        ContribFinder keeps what it needs to recommend projects, until you delete it.{' '}
        <Link to="/privacy" className="text-foreground underline-offset-2 hover:underline">
          What we store and why
        </Link>
      </p>
      <div className="flex flex-wrap gap-3">
        <ConfirmDelete
          trigger="Delete GitHub data"
          title="Delete your GitHub data?"
          description={`This deletes ${GITHUB_DATA}. Your account and GitHub connection stay, so you can sync again from the start.`}
          confirm="Delete data"
          disabled={busy}
          onConfirm={() =>
            deleteData.mutate(undefined, {
              onSuccess: () => navigate('/onboarding', { replace: true }),
            })
          }
        />
        <ConfirmDelete
          trigger="Delete account"
          title="Delete your ContribFinder account?"
          description={`This revokes ContribFinder's access on GitHub and deletes your account, the stored GitHub credential and ${GITHUB_DATA}. It cannot be undone. An audit entry of the deletion is kept without any link to you.`}
          confirm="Delete account"
          disabled={busy}
          onConfirm={() =>
            deleteAccount.mutate(undefined, {
              onSuccess: () => navigate('/', { replace: true }),
            })
          }
        />
      </div>
      {(deleteData.isError || deleteAccount.isError) && (
        <p role="alert" className="text-destructive text-sm">
          That didn&apos;t work. Please try again.
        </p>
      )}
    </section>
  )
}
