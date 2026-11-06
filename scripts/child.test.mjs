import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import { mkdtempSync, readdirSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { pathToFileURL } from 'node:url'

import { pruneRecords, readRecords, withDescendants } from './child.mjs'

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

test(
  'a child without its own process group is stopped by the signal (POSIX)',
  { skip: process.platform === 'win32' && 'POSIX process groups only' },
  async () => {
    const script = `import { runChild } from ${JSON.stringify(childModule)}
runChild(process.execPath, ['-e', 'console.log("ready"); setInterval(() => {}, 1000)'], { detached: false })`
    const runner = spawn(process.execPath, ['--input-type=module', '-e', script], {
      stdio: ['ignore', 'pipe', 'inherit'],
    })
    // The child shares the runner's stdout: its line means both are up, handlers registered.
    await new Promise((resolve) => runner.stdout.once('data', resolve))
    const exited = new Promise((resolve) => runner.on('exit', resolve))
    runner.kill('SIGTERM')
    // Well under GRACE_MS (5 s): the force kill must not be what ends it.
    const timeout = new Promise((resolve) => setTimeout(() => resolve('timeout'), 2_000))
    assert.notEqual(await Promise.race([exited, timeout]), 'timeout')
  },
)

test('pruning drops records of dead processes and unreadable records', () => {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'cf-run-'))
  writeFileSync(path.join(dir, `start-${process.pid}.json`), JSON.stringify({ pid: process.pid }))
  writeFileSync(path.join(dir, 'beat-999999.json'), JSON.stringify({ pid: 999_999 }))
  writeFileSync(path.join(dir, 'broken-1.json'), '{')

  assert.equal(readRecords(dir).length, 3)
  pruneRecords(dir)

  assert.deepEqual(readdirSync(dir), [`start-${process.pid}.json`])
})

test('a tree is a pid with every descendant, however deep, and nothing else', () => {
  const pairs = [
    [10, 1],
    [11, 10],
    [12, 11],
    [13, 10],
    [20, 1],
    [21, 20],
  ]
  assert.deepEqual(withDescendants([10], pairs).sort(), [10, 11, 12, 13])
  assert.deepEqual(withDescendants([12, 20], pairs).sort(), [12, 20, 21])
  assert.deepEqual(withDescendants([99], pairs), [99])
})
