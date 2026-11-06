// Loads the repo-root .env into process.env (existing variables win), like django-environ does.
import { createHash } from 'node:crypto'
import { existsSync, realpathSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

/** Every npm tree with its own lockfile, relative to ``root``: installed by `npm run setup` (in
 * this order: `npm start` needs the root's `concurrently`) and audited by `npm run audit:deps`.
 * The API type generator has its own tree: it needs TypeScript 5, the app 6. CI lists them in
 * `ci.yml` too. */
export const NPM_TREES = ['.', 'apps/frontend', 'apps/frontend/tools/api-types']

/** The module at ``moduleUrl`` is the script node was started with. Compares real paths: Node
 * resolves ``import.meta.url`` through symlinks and junctions but leaves ``argv[1]`` as typed, so
 * a plain comparison would silently skip a CLI (and pass a check) run through a linked path. */
export function isMain(moduleUrl, script = process.argv[1]) {
  if (!script) return false
  try {
    return realpathSync(script) === realpathSync(fileURLToPath(moduleUrl))
  } catch {
    return false
  }
}

export function loadEnv() {
  const file = path.join(root, '.env')
  if (existsSync(file)) process.loadEnvFile(file)
  // Local runners are development; config/celery.py and wsgi.py default to production.
  process.env.DJANGO_SETTINGS_MODULE ||= 'config.settings.development'
}

/** Celery beat's schedule state for the checkout at ``repoRoot``: out of the repository (never in
 * `git status`), and one per checkout, so two checkouts or worktrees never share it. */
export function scheduleFile(repoRoot) {
  const id = createHash('sha1').update(repoRoot).digest('hex').slice(0, 8)
  return path.join(os.tmpdir(), `contribfinder-celerybeat-${id}`)
}

/** Host/port of REDIS_URL, or null when Redis is not configured. */
export function redisTarget() {
  const value = process.env.REDIS_URL?.trim()
  if (!value) return null
  const url = new URL(value)
  // URL keeps an IPv6 host in brackets (`[::1]`); sockets want it bare (SCR-8).
  const hostname = url.hostname.replace(/^\[(.*)\]$/, '$1')
  // Node resolves "localhost" to ::1 first; WSL forwarding and redis bind 127.0.0.1.
  const host = hostname === 'localhost' ? '127.0.0.1' : hostname
  return { host, port: Number(url.port || 6379), isLocal: ['127.0.0.1', '::1'].includes(host) }
}

/** Exits 1 with a message when the module at ``moduleUrl`` was started directly: a library run
 * by mistake must fail, not exit 0 having done nothing (that once passed for a green check). */
export function refuseRun(moduleUrl) {
  if (!isMain(moduleUrl)) return
  const file = path.relative(root, fileURLToPath(moduleUrl)).replaceAll('\\', '/')
  console.error(`${file} is a library used by other scripts; it is not a command.`)
  process.exit(1)
}

refuseRun(import.meta.url)
