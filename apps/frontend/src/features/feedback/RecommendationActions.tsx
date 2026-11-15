import { useMutationState } from '@tanstack/react-query'
import { Bookmark, BookmarkCheck, ChevronDown, EyeOff } from 'lucide-react'
import {
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useEffectEvent,
  useId,
  useRef,
  useState,
} from 'react'

import type { DismissReason, Recommendation } from '@/api/types'
import { Button } from '@/components/ui/button'

import {
  type DismissVariables,
  dismissMutationKey,
  useDismiss,
  useRestore,
  useSave,
  useUnsave,
} from './api'
import { DISMISS_REASON_TEXT, DISMISS_REASONS, FAILED_TEXT } from './messages'
import { usePageVisit } from './visit'

/** Inline text for a failed action, next to its control. */
export function Failed({ children }: { children: ReactNode }) {
  return (
    <span role="status" className="text-destructive text-xs">
      {children}
    </span>
  )
}

export interface DismissedProject {
  repositoryId: number
  name: string
}

export function SaveButton({ recommendation }: { recommendation: Recommendation }) {
  const save = useSave()
  const unsave = useUnsave()
  const { saved } = recommendation
  return (
    <>
      <Button
        variant="outline"
        size="sm"
        aria-pressed={saved}
        // One request at a time: overlapping save and unsave of one card have no order.
        disabled={save.isPending || unsave.isPending}
        onClick={() => {
          save.reset()
          unsave.reset()
          ;(saved ? unsave : save).mutate({
            id: recommendation.id,
            repositoryId: recommendation.repository_id,
          })
        }}
      >
        {saved ? <BookmarkCheck aria-hidden="true" /> : <Bookmark aria-hidden="true" />}
        {saved ? 'Saved' : 'Save'}
      </Button>
      {save.isError && <Failed>{FAILED_TEXT.save}</Failed>}
      {unsave.isError && <Failed>{FAILED_TEXT.unsave}</Failed>}
    </>
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
  const visit = usePageVisit()
  // A failed dismissal brings the card back as a new component, so the error is read from the
  // latest dismissal of this recommendation in the mutation cache, not from `dismiss`. Only
  // from this page visit: a failed mutation stays cached, and its text must not follow the
  // recommendation to its detail page or to a later visit of the list.
  const statuses = useMutationState({
    filters: {
      mutationKey: dismissMutationKey,
      predicate: (m) => {
        const variables = m.state.variables as DismissVariables | undefined
        return variables?.id === recommendation.id && (variables.visit ?? '') === visit
      },
    },
    select: (m) => m.state.status,
  })
  // The card holding these buttons is removed optimistically, and mutate()'s per-call
  // callbacks are skipped once the component unmounts; the mutateAsync promise still settles.
  const run = (reason?: DismissReason) =>
    dismiss
      .mutateAsync({ id: recommendation.id, reason, visit })
      .then(() =>
        onDismissed({
          repositoryId: recommendation.repository_id,
          name: recommendation.repository.full_name,
        }),
      )
      .catch(() => {
        // useDismiss rolls the card back on error.
      })
  return (
    <span className="inline-flex items-center">
      <Button variant="ghost" size="sm" disabled={dismiss.isPending} onClick={() => void run()}>
        <EyeOff aria-hidden="true" />
        Dismiss
      </Button>
      <DismissReasonMenu disabled={dismiss.isPending} onChoose={(reason) => void run(reason)} />
      {statuses.at(-1) === 'error' && <Failed>{FAILED_TEXT.dismiss}</Failed>}
    </span>
  )
}

const MENU_MOVES: Record<string, (at: number, last: number) => number> = {
  ArrowDown: (at) => at + 1,
  ArrowUp: (at) => at - 1,
  Home: () => 0,
  End: (_, last) => last,
}

/** Dismiss with a reason: optional, next to Dismiss, which stays one click. Escape closes
 * the menu and returns focus to its button; a click elsewhere closes it and leaves focus where
 * the user clicked. */
function DismissReasonMenu({
  disabled,
  onChoose,
}: {
  disabled: boolean
  onChoose: (reason: DismissReason) => void
}) {
  const [wantOpen, setOpen] = useState(false)
  // Closed while a dismiss is in flight: a reason chosen then would send a second request.
  const open = wantOpen && !disabled
  const toggle = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLDivElement>(null)
  const menuId = useId()

  const items = () => [...(menu.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])]

  useEffect(() => {
    if (!open) return
    items()[0]?.focus()
    const onOutside = (event: MouseEvent) => {
      const target = event.target as Node
      if (!menu.current?.contains(target) && !toggle.current?.contains(target)) setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [open])

  const onMenuKey = (event: KeyboardEvent) => {
    const all = items()
    const move = MENU_MOVES[event.key]
    if (move) {
      event.preventDefault()
      const at = move(all.indexOf(document.activeElement as HTMLElement), all.length - 1)
      all[(at + all.length) % all.length]?.focus()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      toggle.current?.focus()
    } else if (event.key === 'Tab') {
      setOpen(false)
    }
  }

  return (
    <span className="relative">
      <Button
        ref={toggle}
        variant="ghost"
        size="sm"
        className="px-1.5"
        aria-label="Dismiss with a reason"
        title="Dismiss with a reason"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        disabled={disabled}
        onClick={() => setOpen((was) => !was)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' && !open) {
            event.preventDefault()
            setOpen(true)
          }
        }}
      >
        <ChevronDown aria-hidden="true" />
      </Button>
      {open && (
        <div
          ref={menu}
          id={menuId}
          role="menu"
          aria-label="Dismiss with a reason"
          className="bg-background absolute right-0 z-10 mt-1 flex min-w-40 flex-col rounded-md border p-1 shadow-md"
          onKeyDown={onMenuKey}
        >
          {DISMISS_REASONS.map((reason) => (
            <button
              key={reason}
              type="button"
              role="menuitem"
              tabIndex={-1}
              className="hover:bg-muted focus-visible:bg-muted rounded-sm px-2 py-1.5 text-left text-sm outline-none"
              onClick={() => {
                setOpen(false)
                onChoose(reason)
              }}
            >
              {DISMISS_REASON_TEXT[reason]}
            </button>
          ))}
        </div>
      )}
    </span>
  )
}

export const UNDO_TIMEOUT_MS = 10_000

/** "Hidden … Undo" notice shown for a few seconds after a dismissal. Keyed by the project, so
 * each dismissal starts with fresh undo state. An undo in flight keeps it open; a failed one
 * keeps it 10 s from the failure, so its result is always seen. */
export function DismissUndo({
  project,
  onClose,
}: {
  project: DismissedProject
  onClose: () => void
}) {
  const restore = useRestore()
  // The window runs from the dismissal (this mount): a new onClose (the list re-renders on
  // every filter or page change) must not restart it.
  const [deadline, setDeadline] = useState(() => Date.now() + UNDO_TIMEOUT_MS)
  const close = useEffectEvent(onClose)
  useEffect(() => {
    if (restore.isPending) return
    const timer = setTimeout(() => close(), Math.max(0, deadline - Date.now()))
    return () => clearTimeout(timer)
  }, [deadline, restore.isPending])

  return (
    <div role="status" className="flex flex-wrap items-center gap-3 rounded-md border p-3 text-sm">
      <span>Hidden {project.name}. It won&apos;t be recommended again unless you restore it.</span>
      <Button
        variant="outline"
        size="sm"
        disabled={restore.isPending}
        onClick={() =>
          restore.mutate(project.repositoryId, {
            onSuccess: onClose,
            onError: () => setDeadline(Date.now() + UNDO_TIMEOUT_MS),
          })
        }
      >
        Undo
      </Button>
      {restore.isError && <Failed>{FAILED_TEXT.undo}</Failed>}
    </div>
  )
}
