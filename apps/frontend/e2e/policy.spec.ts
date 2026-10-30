import { CONTENT_SECURITY_POLICY } from '../csp.config.ts'
import { expect, test } from './fixtures.ts'

const IMG_SRC = CONTENT_SECURITY_POLICY.split('; ').find((d) => d.startsWith('img-src '))!

// Canary for the `policyViolations` fixture: if Chromium's wording changes, this fails instead
// of every policy check going silent.
test('a blocked foreign image is recorded as a policy violation', async ({
  page,
  policyViolations,
}) => {
  test.skip(process.env.E2E_DEV_SERVER === '1', 'the dev server sends no policy')
  await page.goto('/')
  // A string, not a function: e2e code is typed without the DOM library.
  await page.evaluate(`{
    const image = document.createElement('img')
    image.src = 'https://example.com/csp-canary.png'
    document.body.append(image)
  }`)

  await expect.poll(() => policyViolations.seen.length).toBeGreaterThan(0)
  expect(policyViolations.take()).toEqual([expect.stringContaining(`"${IMG_SRC}"`)])
})
