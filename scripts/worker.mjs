// `npm run start:worker`: wait for the broker, then run a Celery worker for apps/backend.
import path from 'node:path'

import { runChild } from './child.mjs'
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

// Celery's default prefork pool does not work on Windows; threads do, so a discovery run,
// a profile sync and backlog refreshes run side by side (CELERY_CONCURRENCY, default 4).
const concurrency = process.env.CELERY_CONCURRENCY || '4'
const pool =
  process.platform === 'win32' ? ['--pool=threads', `--concurrency=${concurrency}`] : []
const [cmd, prefix] = uvCommand()
runChild(cmd, [...prefix, 'run', 'celery', '-A', 'config', 'worker', '--loglevel=info', ...pool], {
  cwd: path.join(root, 'apps', 'backend'),
})
