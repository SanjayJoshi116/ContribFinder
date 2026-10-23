// How often a runner may restart a helper that keeps dying (the WSL keep-alive). Pure, so the
// policy is tested without processes.

import { refuseRun } from './env.mjs'

/** At most `max` restarts within any `windowMs`: `allow(now)` records and answers true, or
 * answers false once the budget is spent (older restarts leave the window). */
export function restartBudget({ max = 3, windowMs = 5 * 60_000 } = {}) {
  const times = []
  return {
    allow(now = Date.now()) {
      while (times.length && times[0] <= now - windowMs) times.shift()
      if (times.length >= max) return false
      times.push(now)
      return true
    },
  }
}

refuseRun(import.meta.url)
