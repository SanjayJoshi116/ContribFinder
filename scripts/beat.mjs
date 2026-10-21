// `npm run start:beat`: wait for the broker, then run Celery beat for apps/backend (periodic
// repository staleness and refresh). Embedded `worker -B` is not supported on Windows, so beat
// runs as its own process.
import path from 'node:path'

import { recordProcess, runChild } from './child.mjs'
import { loadEnv, redisTarget, root, scheduleFile } from './env.mjs'
import { uvCommand } from './uv.mjs'
import { waitPort } from './wait-port.mjs'

recordProcess()
loadEnv()
const target = redisTarget()
if (!target) {
  console.log('REDIS_URL is empty; no scheduler without a broker, periodic jobs do not run.')
  process.exit(0)
}

await waitPort(target.host, target.port, 60_000)

const schedule = scheduleFile(root)
const [cmd, prefix] = uvCommand()
runChild(
  cmd,
  [...prefix, 'run', 'celery', '-A', 'config', 'beat', '--loglevel=info', '--schedule', schedule],
  { cwd: path.join(root, 'apps', 'backend') },
)
