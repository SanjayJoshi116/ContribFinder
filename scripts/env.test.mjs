import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { pathToFileURL } from 'node:url'

import { isMain, NPM_TREES, redisTarget, root, scheduleFile } from './env.mjs'

test('each checkout gets its own beat schedule file', () => {
  const one = scheduleFile(String.raw`C:\work\contribfinder`)
  assert.notEqual(one, scheduleFile(String.raw`C:\work\contribfinder-review`))
  assert.equal(one, scheduleFile(String.raw`C:\work\contribfinder`))
  assert.match(one, /contribfinder-celerybeat-[0-9a-f]{8}$/)
})

test('a script started through a linked folder is still the main module', () => {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'cf-ismain-'))
  try {
    const real = path.join(dir, 'real')
    const linked = path.join(dir, 'linked')
    mkdirSync(real)
    writeFileSync(path.join(real, 'cli.mjs'), '')
    writeFileSync(path.join(real, 'other.mjs'), '')
    symlinkSync(real, linked, 'junction')
    const moduleUrl = pathToFileURL(path.join(real, 'cli.mjs')).href

    assert.equal(isMain(moduleUrl, path.join(linked, 'cli.mjs')), true)
    assert.equal(isMain(moduleUrl, path.join(real, 'cli.mjs')), true)
    assert.equal(isMain(moduleUrl, path.join(real, 'other.mjs')), false)
    assert.equal(isMain(moduleUrl, path.join(real, 'missing.mjs')), false)
    assert.equal(isMain(moduleUrl, undefined), false)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('an IPv6 REDIS_URL host is read without brackets and counts as local', (t) => {
  const saved = process.env.REDIS_URL
  t.after(() => {
    if (saved === undefined) delete process.env.REDIS_URL
    else process.env.REDIS_URL = saved
  })
  process.env.REDIS_URL = 'redis://[::1]:6379/1'
  assert.deepEqual(redisTarget(), { host: '::1', port: 6379, isLocal: true })
  process.env.REDIS_URL = 'redis://localhost:6380/1'
  assert.deepEqual(redisTarget(), { host: '127.0.0.1', port: 6380, isLocal: true })
})

test('NPM_TREES is exactly the npm trees with a lockfile, each cached in CI', () => {
  // Tracked and new (not ignored) lockfiles anywhere in the checkout (CR3-7).
  const listed = spawnSync(
    'git',
    ['ls-files', '--cached', '--others', '--exclude-standard', '--', '*package-lock.json'],
    { cwd: root, encoding: 'utf8' },
  )
  assert.equal(listed.status, 0, listed.stderr)
  const lockOf = (tree) => (tree === '.' ? 'package-lock.json' : `${tree}/package-lock.json`)
  const locks = listed.stdout.split('\n').filter(Boolean).sort()
  assert.deepEqual(locks, NPM_TREES.map(lockOf).sort())

  // A whole entry of a `cache-dependency-path` (inline or one per line), never a substring.
  const ci = readFileSync(path.join(root, '.github', 'workflows', 'ci.yml'), 'utf8')
  const entries = new Set(
    ci.split(/\r?\n/).map((line) => line.trim().replace(/^cache-dependency-path:\s*/, '')),
  )
  for (const lock of locks) assert.ok(entries.has(lock), `ci.yml caches ${lock}`)
})
