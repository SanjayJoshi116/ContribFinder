// Fails when VERSION and the package manifests or lockfiles disagree (`npm run check:version`, CI).
import { readFileSync } from 'node:fs'
import path from 'node:path'

import { isMain, root } from './env.mjs'

/** An npm lockfile's versions, keyed by where they sit: the top level and the root package
 * entry (`packages[""]`), which `npm install` updates separately. */
export function lockfileVersions(file, text) {
  const lock = JSON.parse(text)
  return {
    [file]: lock.version,
    [`${file} packages[""]`]: lock.packages?.['']?.version,
  }
}

/** ``[location, version]`` pairs that differ from ``expected``. */
export function mismatches(found, expected) {
  return Object.entries(found).filter(([, version]) => version !== expected)
}

if (isMain(import.meta.url)) {
  const read = (file) => readFileSync(path.join(root, file), 'utf8')

  const expected = read('VERSION').trim()
  const found = {
    'package.json': JSON.parse(read('package.json')).version,
    'apps/frontend/package.json': JSON.parse(read('apps/frontend/package.json')).version,
    'apps/backend/pyproject.toml': read('apps/backend/pyproject.toml').match(
      /^version = "(.+)"$/m,
    )?.[1],
    // Lockfiles too: CI installs with `npm ci` / `uv sync --frozen`, which reject stale locks.
    ...lockfileVersions('package-lock.json', read('package-lock.json')),
    ...lockfileVersions('apps/frontend/package-lock.json', read('apps/frontend/package-lock.json')),
    'apps/backend/uv.lock': read('apps/backend/uv.lock').match(
      /name = "contribfinder-backend"\r?\nversion = "(.+)"/,
    )?.[1],
  }

  const wrong = mismatches(found, expected)
  if (wrong.length) {
    for (const [where, version] of wrong) {
      console.error(`${where}: ${version ?? '(missing)'} != VERSION ${expected}`)
    }
    process.exit(1)
  }
  console.log(`Version ${expected} consistent across ${Object.keys(found).length + 1} entries.`)
}
