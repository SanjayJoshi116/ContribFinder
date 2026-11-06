// `npm run manage -- <command> [args]`: run a Django management command in apps/backend,
// finding uv the same way `npm start` does (no need for uv on PATH).
import path from 'node:path'

import { root } from './env.mjs'
import { uv } from './uv.mjs'

const backend = path.join(root, 'apps', 'backend')
const args = process.argv.slice(2)
if (args.length === 0) {
  console.error(
    'Usage: npm run manage -- <command> [args], e.g. npm run manage -- reanalyze_profiles',
  )
  process.exit(2)
}
uv(['run', 'python', 'manage.py', ...args], { cwd: backend })
