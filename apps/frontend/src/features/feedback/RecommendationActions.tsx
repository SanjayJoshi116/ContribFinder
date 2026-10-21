import { Bookmark, BookmarkCheck, EyeOff } from 'lucide-react'
import { useEffect } from 'react'

import type { Recommendation } from '@/api/types'
import { Button } from '@/components/ui/button'

import { useDismiss, useRestore, useSave, useUnsave } from './api'

export interface DismissedProject {
  repositoryId: number
  name: string
}

export function SaveButton({ recommendation }: { recommendation: Recommendation }) {
  const save = useSave()
  const unsave = useUnsave()
  const { saved } = recommendation
  return (
    <Button
      variant="outline"
      size="sm"
      aria-pressed={saved}
      // One request at a time: overlapping save and unsave have no order, and each rollback
      // would restore a snapshot taken before the other.
      disabled={save.isPending || unsave.isPending}
      onClick={() => (saved ? unsave : save).mutate(recommendation.id)}
    >
      {saved ? <BookmarkCheck aria-hidden="true" /> : <Bookmark aria-hidden="true" />}
      {saved ? 'Saved' : 'Save'}
    </Button>
  )
}

export function DismissButton({
  recommendation,
  onDismissed,
}: {
  recommendation: Recommendation
  onDismissed: (project: DismissedProject) => void
}) {
  const dismiss = useDismiss()
  return (
    <Button
      variant="ghost"
      size="sm"
      disabled={dismiss.isPending}
      // The card holding this button is removed optimistically, and mutate()'s per-call
      // callbacks are skipped once the component unmounts; the mutateAsync promise still settles.
      onClick={() =>
        dismiss
          .mutateAsync(recommendation.id)
          .then(() =>
            onDismissed({
              repositoryId: recommendation.repository_id,
              name: recommendation.repository.full_name,
            }),
          )
          .catch(() => {
            // useDismiss rolls the card back on error.
          })
      }
    >
      <EyeOff aria-hidden="true" />
      Dismiss
    </Button>
  )
}

export const UNDO_TIMEOUT_MS = 10_000

/** "Hidden … Undo" notice shown for a few seconds after a dismissal. */
export function DismissUndo({
  project,
  onClose,
}: {
  project: DismissedProject
  onClose: () => void
}) {
  const restore = useRestore()
  useEffect(() => {
    const timer = setTimeout(onClose, UNDO_TIMEOUT_MS)
    return () => clearTimeout(timer)
  }, [project, onClose])

  return (
    <div role="status" className="flex flex-wrap items-center gap-3 rounded-md border p-3 text-sm">
      <span>Hidden {project.name}. It won&apos;t be recommended again unless you restore it.</span>
      <Button
        variant="outline"
        size="sm"
        disabled={restore.isPending}
        onClick={() => restore.mutate(project.repositoryId, { onSuccess: onClose })}
      >
        Undo
      </Button>
      {restore.isError && <span className="text-destructive">Undo didn&apos;t work.</span>}
    </div>
  )
}
