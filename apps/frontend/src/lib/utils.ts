import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** A route `:id` as a positive integer, or null for anything else ("abc", "0", "1.5", "0x1f",
 * "1e2", " 7"). */
export function positiveId(param: string | undefined): number | null {
  if (!param || !/^[1-9]\d*$/.test(param)) return null
  const id = Number(param)
  return Number.isSafeInteger(id) ? id : null
}
