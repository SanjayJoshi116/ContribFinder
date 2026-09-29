// `npm run start:redis` (Windows): make sure the WSL redis-server service runs, and keep the
// distro awake for as long as this process lives (WSL stops idle distros, and Redis with them).
import { spawn, spawnSync } from 'node:child_process'

import { watchStack } from './child.mjs'
import { loadEnv, redisTarget } from './env.mjs'
import { waitPort } from './wait-port.mjs'

loadEnv()
const target = redisTarget()
const distro = process.env.WSL_DISTRO ?? 'Ubuntu'

function wsl(args, options = {}) {
  return spawnSync('wsl.exe', ['-d', distro, ...args], { encoding: 'utf8', ...options })
}

if (!target) {
  console.log('REDIS_URL is empty; not starting Redis.')
  process.exit(0)
}

const check = wsl(['-u', 'root', '--', 'sh', '-c', 'command -v redis-server'])
if (check.error || check.status !== 0) {
  console.error(
    `redis-server not found in WSL distro "${distro}". Install it with:\n` +
      `  wsl -d ${distro} -u root -- apt-get install -y redis-server`,
  )
  process.exit(1)
}

const started = wsl(['-u', 'root', '--', 'systemctl', 'start', 'redis-server'])
if (started.status !== 0) {
  console.error(`Could not start redis-server in WSL:\n${started.stderr}`)
  process.exit(1)
}

// An attached session keeps the distro (and the redis-server service) running.
const keepAlive = spawn('wsl.exe', ['-d', distro, '--', 'sleep', 'infinity'], { stdio: 'ignore' })
const stop = () => {
  keepAlive.kill()
  process.exit(0)
}
process.on('SIGINT', stop)
process.on('SIGTERM', stop)
watchStack(stop)
keepAlive.on('exit', (code) => {
  console.error(`WSL keep-alive session ended (code ${code}); Redis may stop.`)
  process.exit(1)
})

try {
  await waitPort(target.host, target.port)
  console.log(`Redis ready at ${target.host}:${target.port} (WSL ${distro})`)
} catch (error) {
  console.error(
    `${error.message}. WSL localhost forwarding may be disabled; set REDIS_URL to the ` +
      `WSL IP (wsl hostname -I) instead.`,
  )
  stop()
}
