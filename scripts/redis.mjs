// `npm run start:redis` (Windows): make sure the WSL redis-server service runs, and keep the
// distro awake for as long as this process lives (WSL stops idle distros, and Redis with them).
import { spawn } from 'node:child_process'

import { recordProcess, removeRecord, watchStack } from './child.mjs'
import { loadEnv, redisTarget } from './env.mjs'
import { restartBudget } from './restarts.mjs'
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

// An attached session keeps the distro (and the redis-server service) running. One that ends
// while the stack runs is replaced (a stray console event once ended it); a session that keeps
// ending fails the runner as before.
const restarts = restartBudget()
let keepAlive
let stopping = false

function startKeepAlive() {
  const session = spawn('wsl.exe', ['-d', distro, '--', 'sleep', 'infinity'], {
    ...WSL_OPTIONS,
    stdio: 'ignore',
  })
  // Detached for its own hidden console (see WSL_OPTIONS). On Windows it is still this runner's
  // child, so killing the runner's tree ends it too; the record lets `npm run stop` find it when
  // the runner is already gone. A failed spawn has no pid and nothing to record.
  const record =
    typeof session.pid === 'number'
      ? recordProcess({ pid: session.pid, exe: 'wsl', marker: 'sleep infinity' })
      : null
  session.on('exit', (code) => {
    if (record) removeRecord(record)
    if (stopping) return
    const shown = code === null ? 'none' : `${code}, 0x${(code >>> 0).toString(16).toUpperCase()}`
    if (!restarts.allow()) {
      console.error(`WSL keep-alive ended again (code ${shown}): 4 times in 5 minutes; giving up.`)
      process.exit(1)
    }
    console.error(`WSL keep-alive session ended (code ${shown}); starting a new one.`)
    keepAlive = startKeepAlive()
  })
  return session
}

keepAlive = startKeepAlive()
const stop = () => {
  stopping = true
  keepAlive.kill()
  process.exit(0)
}
// SIGHUP: the console window was closed.
for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(signal, stop)
watchStack(stop)

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
