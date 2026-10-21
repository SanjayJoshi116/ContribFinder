// `npm run start:redis` (Windows): make sure the WSL redis-server service runs, and keep the
// distro awake for as long as this process lives (WSL stops idle distros, and Redis with them).
import { spawn } from 'node:child_process'

import { recordProcess, watchStack } from './child.mjs'
import { loadEnv, redisTarget } from './env.mjs'
import { waitPort } from './wait-port.mjs'

recordProcess()
loadEnv()
const target = redisTarget()
const distro = process.env.WSL_DISTRO ?? 'Ubuntu'

// Every wsl.exe gets its own hidden console (detached): wsl.exe switches its console's input to raw
// VT mode, which on the shared `npm start` console turned Ctrl+C into a plain keystroke.
const WSL_OPTIONS = { detached: true, windowsHide: true }

/** Run a short wsl.exe command; resolves to ``{ status, stderr, error }``. */
function wsl(args) {
  return new Promise((resolve) => {
    const child = spawn('wsl.exe', ['-d', distro, ...args], {
      ...WSL_OPTIONS,
      stdio: ['ignore', 'ignore', 'pipe'],
    })
    let stderr = ''
    child.stderr.setEncoding('utf8').on('data', (chunk) => (stderr += chunk))
    child.on('error', (error) => resolve({ status: null, stderr, error }))
    child.on('close', (status) => resolve({ status, stderr }))
  })
}

if (!target) {
  console.log('REDIS_URL is empty; not starting Redis.')
  process.exit(0)
}

const check = await wsl(['-u', 'root', '--', 'sh', '-c', 'command -v redis-server'])
if (check.error || check.status !== 0) {
  console.error(
    `redis-server not found in WSL distro "${distro}". Install it with:\n` +
      `  wsl -d ${distro} -u root -- apt-get install -y redis-server`,
  )
  process.exit(1)
}

const started = await wsl(['-u', 'root', '--', 'systemctl', 'start', 'redis-server'])
if (started.status !== 0) {
  console.error(`Could not start redis-server in WSL:\n${started.stderr}`)
  process.exit(1)
}

// An attached session keeps the distro (and the redis-server service) running.
const keepAlive = spawn('wsl.exe', ['-d', distro, '--', 'sleep', 'infinity'], {
  ...WSL_OPTIONS,
  stdio: 'ignore',
})
// Detached, so it is not in this runner's process tree: `npm run stop` finds it by its record.
recordProcess({ pid: keepAlive.pid, exe: 'wsl', marker: 'sleep infinity' })
const stop = () => {
  keepAlive.kill()
  process.exit(0)
}
// SIGHUP: the console window was closed.
for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(signal, stop)
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
