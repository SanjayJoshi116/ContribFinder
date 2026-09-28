// `npm run start:backend`: apply migrations, then run the Django dev server on :8000.
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'

import { uv, uvCommand } from './uv.mjs'

const backend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'apps', 'backend')

uv(['run', 'python', 'manage.py', 'migrate', '--noinput'], { cwd: backend })

const [cmd, prefix] = uvCommand()
const server = spawn(cmd, [...prefix, 'run', 'python', 'manage.py', 'runserver', '8000'], {
  cwd: backend,
  stdio: 'inherit',
})
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.kill(signal))
server.on('exit', (code) => process.exit(code ?? 0))
