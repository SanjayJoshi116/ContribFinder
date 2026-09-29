// `npm start`: run the local stack. With REDIS_URL set: Redis (WSL on Windows), Django, a Celery
// worker and Vite. Without it: Django and Vite only, and Celery tasks run inline (blocking).
import concurrently from 'concurrently'

import { loadEnv, redisTarget, root } from './env.mjs'

loadEnv()
const target = redisTarget()
const commands = []

if (target?.isLocal && process.platform === 'win32') {
  commands.push({ name: 'redis', command: 'node scripts/redis.mjs', prefixColor: 'red' })
}
commands.push({ name: 'backend', command: 'node scripts/backend.mjs', prefixColor: 'blue' })
if (target) {
  commands.push({ name: 'worker', command: 'node scripts/worker.mjs', prefixColor: 'yellow' })
} else {
  console.warn(
    'REDIS_URL is empty: background jobs run inline, so GitHub syncs block the request.\n' +
      'Set REDIS_URL in .env (see README) for real background processing.\n',
  )
}
commands.push({
  name: 'frontend',
  command: 'npm --prefix apps/frontend run dev',
  prefixColor: 'magenta',
})

const { result } = concurrently(commands, { cwd: root, killOthersOn: ['failure'], prefix: 'name' })
result.catch(() => process.exit(1))
