import assert from 'node:assert/strict'
import { test } from 'node:test'

import { restartBudget } from './restarts.mjs'

test('allows max restarts within the window, then refuses', () => {
  const budget = restartBudget({ max: 3, windowMs: 1000 })
  assert.deepEqual(
    [0, 100, 200, 300].map((t) => budget.allow(t)),
    [true, true, true, false],
  )
})

test('restarts that left the window free the budget again', () => {
  const budget = restartBudget({ max: 2, windowMs: 1000 })
  assert.equal(budget.allow(0), true)
  assert.equal(budget.allow(500), true)
  assert.equal(budget.allow(900), false)
  assert.equal(budget.allow(1000), true) // the restart at 0 is out of the window
  assert.equal(budget.allow(1100), false)
})
