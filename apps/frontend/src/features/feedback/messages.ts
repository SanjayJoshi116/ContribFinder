import type { DismissReason } from '@/api/types'

/** Why a project was hidden, in menu order. Recorded and reported, never used for ranking. */
export const DISMISS_REASON_TEXT: Record<DismissReason, string> = {
  not_my_stack: 'Not my stack',
  too_big: 'Too big',
  inactive: 'Inactive',
  already_know: 'Already know it',
}

export const DISMISS_REASONS = Object.keys(DISMISS_REASON_TEXT) as DismissReason[]

/** Shown next to the control whose request failed; cleared when it is tried again. */
export const FAILED_TEXT = {
  save: "Couldn't save.",
  // Unsaving takes the project off the saved list, the same as Remove there.
  unsave: "Couldn't remove.",
  dismiss: "Couldn't hide.",
  remove: "Couldn't remove.",
  restore: "Couldn't restore.",
  undo: "Undo didn't work.",
  more: "Couldn't load more.",
} as const
