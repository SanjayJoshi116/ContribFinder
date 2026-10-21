import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { pathToFileURL } from 'node:url'

import { isMain, scheduleFile } from './env.mjs'

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
