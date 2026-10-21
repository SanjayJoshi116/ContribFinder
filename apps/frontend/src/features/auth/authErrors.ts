/** Messages for ?auth_error=<code> set by the OAuth callback redirect. */
const MESSAGES: Record<string, string> = {
  cancelled: 'GitHub sign-in was cancelled. You can try again whenever you are ready.',
  invalid_state: 'Your sign-in session expired or was interrupted. Please try again.',
  failed: 'We could not complete sign-in with GitHub. Please try again in a moment.',
  session_ended: 'Your session ended. Sign in again to pick up where you left off.',
}

/** Where the app goes when a signed-in request answers 401. */
export const SESSION_ENDED_PATH = '/?auth_error=session_ended'

export function authErrorMessage(code: string | null): string | null {
  if (!code) return null
  return MESSAGES[code] ?? MESSAGES.failed
}
