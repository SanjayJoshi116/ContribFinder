// `npm run setup`: one-time local setup without Docker.
//   1. Create .env from .env.example with generated secrets (never overwrites an existing .env)
//   2. Install backend deps (uv) and every npm tree (`NPM_TREES`, `npm ci` as CI: lockfiles
//      stay untouched)
//   3. Apply database migrations (needs the local PostgreSQL role/database, see README)
import { randomBytes } from 'node:crypto'
import { copyFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import path from 'node:path'

import { NPM_TREES, root } from './env.mjs'
import { uv } from './uv.mjs'

const envPath = path.join(root, '.env')

if (existsSync(envPath)) {
  console.log('.env exists; leaving it unchanged.')
} else {
  copyFileSync(path.join(root, '.env.example'), envPath)
  // Fernet key: 32 random bytes, URL-safe base64 with padding.
  const fernetKey = randomBytes(32).toString('base64').replace(/\+/g, '-').replace(/\//g, '_')
  const secretKey = randomBytes(48).toString('base64url')
  const env = readFileSync(envPath, 'utf8')
    .replace(/^DJANGO_SECRET_KEY=.*$/m, `DJANGO_SECRET_KEY=${secretKey}`)
    .replace(/^TOKEN_ENCRYPTION_KEYS=.*$/m, `TOKEN_ENCRYPTION_KEYS=${fernetKey}`)
  writeFileSync(envPath, env)
  console.log('Created .env with generated DJANGO_SECRET_KEY and TOKEN_ENCRYPTION_KEYS.')
  console.log('Add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to .env before signing in.')
}

const backend = path.join(root, 'apps', 'backend')
uv(['sync'], { cwd: backend })

// Single command string: npm is a .cmd shim on Windows and needs a shell; no args to escape.
for (const tree of NPM_TREES) {
  const npm = spawnSync('npm ci', { cwd: path.join(root, tree), stdio: 'inherit', shell: true })
  if (npm.status !== 0) process.exit(npm.status ?? 1)
}

uv(['run', 'python', 'manage.py', 'migrate', '--noinput'], { cwd: backend })
console.log('\nSetup complete. Run `npm start`.')
