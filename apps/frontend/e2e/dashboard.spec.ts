import type { Page } from '@playwright/test'

import { expect, test, type SeededUser } from './fixtures.ts'

type SignIn = (user: SeededUser) => Promise<void>

/** Tests that change data sign in as their own user; the rest read `e2e-dashboard`. */
async function dashboard(page: Page, signInAs: SignIn, user: SeededUser = 'e2e-dashboard') {
  await signInAs(user)
  await page.goto('/app')
}

test('shows the profile and labeled recommendations, never a percentage', async ({
  page,
  signInAs,
}) => {
  await dashboard(page, signInAs)
  await expect(page.getByRole('heading', { name: 'Skills' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Skills' })).toContainText('Python')
  const cards = page.getByRole('article')
  await expect(cards).toHaveCount(20)
  const first = page.getByRole('article', { name: 'project-01' })
  await expect(first).toContainText(/(Strong|Good|Partial) match/)
  await expect(page.getByRole('region', { name: 'Recommended projects' })).not.toContainText('%')
  await expect(page.getByRole('navigation', { name: 'Recommendation pages' })).toBeVisible()
})

test('saves a project and lists it on the saved page', async ({ page, signInAs }) => {
  await dashboard(page, signInAs, 'e2e-save')
  const card = page.getByRole('article', { name: 'project-03' })
  await card.getByRole('button', { name: 'Save' }).click()
  await expect(card.getByRole('button', { name: 'Saved' })).toBeEnabled()

  await page.getByRole('link', { name: 'Saved and hidden projects' }).click()
  await expect(page.getByRole('article', { name: 'seed-org/project-03' })).toBeVisible()
})

test('dismisses a project and brings it back with Undo', async ({ page, signInAs }) => {
  await dashboard(page, signInAs, 'e2e-dismiss')
  const card = page.getByRole('article', { name: 'project-07' })
  // Exact: "Dismiss with a reason" is a second button on the card.
  await card.getByRole('button', { name: 'Dismiss', exact: true }).click()
  await expect(card).toBeHidden()
  const notice = page.getByRole('status').filter({ hasText: 'Hidden seed-org/project-07' })

  await notice.getByRole('button', { name: 'Undo' }).click()

  // Restore regenerates (inline in these tests), which brings the project back.
  await expect(page.getByRole('article', { name: 'project-07' })).toBeVisible()
  await page.goto('/app/saved')
  await expect(page.getByText('No hidden projects.')).toBeVisible()
})

test('the relevant-issues link lands on the issues', async ({ page, signInAs }) => {
  await dashboard(page, signInAs)
  const card = page.getByRole('article', { name: 'project-01' })
  await card.getByRole('link', { name: /relevant issues/ }).click()

  const heading = page.getByRole('heading', { name: 'Relevant issues' })
  await expect(heading).toBeFocused()
  await expect(heading).toBeInViewport()
})
