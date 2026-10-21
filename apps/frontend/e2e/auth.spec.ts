import { expect, test } from './fixtures.ts'

test('sign-in starts at GitHub with a state', async ({ page }) => {
  const response = await page.request.get('/api/v1/auth/github', { maxRedirects: 0 })

  expect(response.status()).toBe(302)
  const location = new URL(response.headers()['location']!)
  expect(location.pathname).toBe('/login/oauth/authorize')
  expect(location.searchParams.get('state')).toBeTruthy()
  expect(location.searchParams.get('client_id')).toBe('e2e-client-id')
})

test('a signed-in user without synced data lands on onboarding', async ({ page, signInAs }) => {
  await signInAs('e2e-unsynced')
  await page.goto('/app')

  await expect(page).toHaveURL(/\/onboarding$/)
  await expect(page.getByRole('button', { name: 'Start sync' })).toBeVisible()
})

test('an ended session returns to sign-in with a notice', async ({ page, context, signInAs }) => {
  await signInAs('e2e-dashboard')
  await page.goto('/app')
  const card = page.getByRole('article', { name: 'project-05' })
  await expect(card).toBeVisible()

  await context.clearCookies()
  await card.getByRole('link', { name: 'project-05' }).click()

  await expect(page.getByRole('alert')).toHaveText(/your session ended/i)
  await expect(page).toHaveURL(/\/\?auth_error=session_ended$/)
  await expect(page.getByRole('link', { name: 'Continue with GitHub' })).toBeVisible()
})
