// Fails when VERSION and the package manifests or lockfiles disagree (`npm run check:version`, CI).
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (file) => readFileSync(path.join(root, file), 'utf8')

const expected = read('VERSION').trim()
const found = {
  'package.json': JSON.parse(read('package.json')).version,
  'apps/frontend/package.json': JSON.parse(read('apps/frontend/package.json')).version,
  'apps/backend/pyproject.toml': read('apps/backend/pyproject.toml').match(
    /^version = "(.+)"$/m,
  )?.[1],
  // Lockfiles too: CI installs with `npm ci` / `uv sync --frozen`, which reject stale locks.
  'package-lock.json': JSON.parse(read('package-lock.json')).version,
  'apps/frontend/package-lock.json': JSON.parse(read('apps/frontend/package-lock.json')).version,
  'apps/backend/uv.lock': read('apps/backend/uv.lock').match(
    /name = "contribfinder-backend"\r?\nversion = "(.+)"/,
  )?.[1],
}

const mismatches = Object.entries(found).filter(([, version]) => version !== expected)
if (mismatches.length) {
  for (const [file, version] of mismatches) {
    console.error(`${file}: ${version ?? '(missing)'} != VERSION ${expected}`)
  }
  process.exit(1)
}
console.log(`Version ${expected} consistent across ${Object.keys(found).length + 1} files.`)
