import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { test } from 'node:test'

import { root } from './env.mjs'

// Library modules fail loudly when started directly (spec developer-tooling, "Library scripts
// refuse to run as commands"); importing them, as every other test file does, is unaffected.
for (const name of ['child', 'env', 'restarts', 'stack', 'uv']) {
  test(`scripts/${name}.mjs refuses to run as a command`, () => {
    const result = spawnSync(process.execPath, [path.join(root, 'scripts', `${name}.mjs`), 'run'], {
      encoding: 'utf8',
    })
    assert.equal(result.status, 1)
    assert.ok(result.stderr.includes(`scripts/${name}.mjs is a library`), result.stderr)
    assert.equal(result.stdout, '')
  })
}
