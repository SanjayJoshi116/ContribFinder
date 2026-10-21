// Backend for the browser tests (`npm run e2e` in apps/frontend, started by Playwright):
// create, migrate and seed the contribfinder_e2e database, then serve it on :8001. Uses
// config.settings.e2e, the only settings with the seed command; sessions go to argv[2].
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { parseEnv } from 'node:util'

import { runChild } from './child.mjs'
import { root } from './env.mjs'
import { uv, uvCommand } from './uv.mjs'

// The tests see CI's settings: of a local .env only DATABASE_URL (where PostgreSQL is) is used,
// and Django does not read .env itself. Children inherit this environment.
const dotenv = path.join(root, '.env')
if (!process.env.DATABASE_URL && existsSync(dotenv)) {
  const { DATABASE_URL } = parseEnv(readFileSync(dotenv, 'utf8'))
  if (DATABASE_URL) process.env.DATABASE_URL = DATABASE_URL
}
process.env.DJANGO_READ_DOTENV = '0'

const backend = path.join(root, 'apps', 'backend')
const settings = ['--settings', 'config.settings.e2e']
const sessions = process.argv[2]
if (!sessions) {
  console.error('Usage: node scripts/e2e-backend.mjs <sessions.json>')
  process.exit(2)
}

uv(['run', 'python', 'manage.py', 'e2e_seed', '--out', path.resolve(sessions), ...settings], {
  cwd: backend,
})

const [cmd, prefix] = uvCommand()
runChild(
  cmd,
  [...prefix, 'run', 'python', 'manage.py', 'runserver', '127.0.0.1:8001', '--noreload', ...settings],
  { cwd: backend },
)
