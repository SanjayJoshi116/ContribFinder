import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readdirSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { pathToFileURL } from 'node:url'

import { pruneRecords, readRecords } from './child.mjs'

const childModule = pathToFileURL(path.join(import.meta.dirname, 'child.mjs')).href

test('a program that cannot be started ends the runner with a message', () => {
  const script = `import { runChild } from ${JSON.stringify(childModule)}
runChild(${JSON.stringify(path.join(os.tmpdir(), 'no-such-program-cf'))}, [])`
  const result = spawnSync(process.execPath, ['--input-type=module', '-e', script], {
    encoding: 'utf8',
  })
  assert.equal(result.status, 1)
  assert.match(result.stderr, /^Could not start .*no-such-program-cf: /m)
  assert.doesNotMatch(result.stderr, /Unhandled 'error' event/)
})

test('pruning drops records of dead processes and unreadable records', () => {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'cf-run-'))
  writeFileSync(path.join(dir, `start-${process.pid}.json`), JSON.stringify({ pid: process.pid }))
  writeFileSync(path.join(dir, 'beat-999999.json'), JSON.stringify({ pid: 999_999 }))
  writeFileSync(path.join(dir, 'broken-1.json'), '{')

  assert.equal(readRecords(dir).length, 3)
  pruneRecords(dir)

  assert.deepEqual(readdirSync(dir), [`start-${process.pid}.json`])
})
