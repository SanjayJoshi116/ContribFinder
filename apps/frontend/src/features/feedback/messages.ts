import type { DismissReason } from '@/api/types'

/** Why a project was hidden, in menu order. Recorded and reported, never used for ranking. */
export const DISMISS_REASON_TEXT: Record<DismissReason, string> = {
  not_my_stack: 'Not my stack',
  too_big: 'Too big',
  inactive: 'Inactive',
  already_know: 'Already know it',
}

export const DISMISS_REASONS = Object.keys(DISMISS_REASON_TEXT) as DismissReason[]
