import assert from 'node:assert/strict'
import { test } from 'node:test'

import { lockfileVersions, mismatches } from './check-version.mjs'

const lock = (top, root) => JSON.stringify({ version: top, packages: { '': { version: root } } })

test('a half-updated lockfile is reported by its root package entry', () => {
  const found = lockfileVersions('package-lock.json', lock('0.12.9', '0.12.8'))
  assert.deepEqual(mismatches(found, '0.12.9'), [['package-lock.json packages[""]', '0.12.8']])
})

test('a consistent lockfile passes', () => {
  assert.deepEqual(mismatches(lockfileVersions('x', lock('1.0.0', '1.0.0')), '1.0.0'), [])
})

test('a lockfile without a root package entry is reported as missing', () => {
  const found = lockfileVersions('x', JSON.stringify({ version: '1.0.0' }))
  assert.deepEqual(mismatches(found, '1.0.0'), [['x packages[""]', undefined]])
})
