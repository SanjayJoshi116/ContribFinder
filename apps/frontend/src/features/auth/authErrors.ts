/** Messages for ?auth_error=<code> set by the OAuth callback redirect. */
const MESSAGES: Record<string, string> = {
  cancelled: 'GitHub sign-in was cancelled. You can try again whenever you are ready.',
  invalid_state: 'Your sign-in session expired or was interrupted. Please try again.',
  failed: 'We could not complete sign-in with GitHub. Please try again in a moment.',
}

export function authErrorMessage(code: string | null): string | null {
  if (!code) return null
  return MESSAGES[code] ?? MESSAGES.failed
}
