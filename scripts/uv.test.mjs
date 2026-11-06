import assert from 'node:assert/strict'
import { test } from 'node:test'

import { newestPythonFirst } from './uv.mjs'

test('Python install folders are searched newest version first', () => {
  assert.deepEqual(newestPythonFirst(['Python39', 'Python313', 'Launcher', 'Python312']), [
    'Python313',
    'Python312',
    'Python39',
    'Launcher',
  ])
})
