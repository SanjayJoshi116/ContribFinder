// `npm start`: run the local stack. With REDIS_URL set: Redis (WSL on Windows), Django, a Celery
// worker, Celery beat and Vite. Without it: Django and Vite only, and Celery tasks run inline
// (blocking) with no periodic jobs.
import concurrently from 'concurrently'

import { loadEnv, redisTarget, root } from './env.mjs'

loadEnv()
// Runners stop their process trees when this process is gone (scripts/child.mjs).
process.env.CF_STACK_PID = String(process.pid)
const target = redisTarget()
const commands = []

if (target?.isLocal && process.platform === 'win32') {
  commands.push({ name: 'redis', command: 'node scripts/redis.mjs', prefixColor: 'red' })
}
commands.push({ name: 'backend', command: 'node scripts/backend.mjs', prefixColor: 'blue' })
if (target) {
  commands.push({ name: 'worker', command: 'node scripts/worker.mjs', prefixColor: 'yellow' })
  commands.push({ name: 'beat', command: 'node scripts/beat.mjs', prefixColor: 'green' })
} else {
  console.warn(
    'REDIS_URL is empty: background jobs run inline, so GitHub syncs block the request.\n' +
      'Set REDIS_URL in .env (see README) for real background processing.\n',
  )
}
commands.push({
  name: 'frontend',
  command: 'node scripts/frontend.mjs',
  prefixColor: 'magenta',
})

const { result } = concurrently(commands, { cwd: root, killOthersOn: ['failure'], prefix: 'name' })
result.catch(() => process.exit(1))

// concurrently kills every process tree on Ctrl+C; never hang here if one refuses to go.
// Leftovers from an earlier run: `npm run stop`.
for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  process.on(signal, () => setTimeout(() => process.exit(130), 10_000).unref())
}
