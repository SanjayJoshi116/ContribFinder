// `npm run start:worker`: wait for the broker, then run a Celery worker for apps/backend.
import { spawn } from 'node:child_process'
import path from 'node:path'

import { loadEnv, redisTarget, root } from './env.mjs'
import { uvCommand } from './uv.mjs'
import { waitPort } from './wait-port.mjs'

loadEnv()
const target = redisTarget()
if (!target) {
  console.log('REDIS_URL is empty; tasks run inline in Django, no worker needed.')
  process.exit(0)
}

await waitPort(target.host, target.port, 60_000)

// Celery's default prefork pool does not work on Windows.
const pool = process.platform === 'win32' ? ['--pool=solo'] : []
const [cmd, prefix] = uvCommand()
const worker = spawn(
  cmd,
  [...prefix, 'run', 'celery', '-A', 'config', 'worker', '--loglevel=info', ...pool],
  { cwd: path.join(root, 'apps', 'backend'), stdio: 'inherit' },
)
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => worker.kill(signal))
worker.on('exit', (code) => process.exit(code ?? 0))
