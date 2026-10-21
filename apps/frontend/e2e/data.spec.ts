import { expect, test } from './fixtures.ts'

test('deleting GitHub data returns to onboarding', async ({ page, signInAs }) => {
  await signInAs('e2e-delete')
  await page.goto('/app')

  await page.getByRole('button', { name: 'Delete GitHub data' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Delete data' }).click()

  await expect(page).toHaveURL(/\/onboarding$/)
  await expect(page.getByRole('button', { name: 'Start sync' })).toBeVisible()
})
