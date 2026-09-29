// Run a long-lived child (Django, Celery) and make sure it stops, with everything it started,
// when this runner is stopped. On Windows, Ctrl+C already reaches the child through the shared
// console; killing only the direct child (uv.exe) would orphan celery/python grandchildren, so
// the runner waits for a clean exit and then kills the whole process tree.
import { spawn, spawnSync } from 'node:child_process'

const GRACE_MS = 5_000

/** Force-kill a process and all its descendants. */
export function killTree(pid) {
  if (pid === undefined) return
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    try {
      process.kill(-pid, 'SIGKILL') // the child leads its own process group (detached)
    } catch {
      // already gone
    }
  }
}

function alive(pid) {
  try {
    process.kill(pid, 0)
    return true
  } catch (error) {
    return error.code === 'EPERM'
  }
}

/** Call ``onGone`` once the ``npm start`` process (``CF_STACK_PID``) is gone. Some terminals
 * (Git Bash/mintty) end only the top process on Ctrl+C; without this its children run on. */
export function watchStack(onGone) {
  const pid = Number(process.env.CF_STACK_PID)
  if (!pid) return
  const timer = setInterval(() => {
    if (!alive(pid)) {
      clearInterval(timer)
      onGone()
    }
  }, 1_000)
  timer.unref()
}

/** Spawn ``cmd args`` with inherited stdio; exit with it; stop it on SIGINT/SIGTERM/SIGHUP.
 * The first signal allows ``GRACE_MS`` for a clean shutdown, a second one kills at once. */
export function runChild(cmd, args, options = {}) {
  const posix = process.platform !== 'win32'
  const child = spawn(cmd, args, { stdio: 'inherit', detached: posix, ...options })
  let stopping = false
  const stop = (signal) => {
    if (stopping) {
      killTree(child.pid)
      return
    }
    stopping = true
    if (posix) process.kill(-child.pid, signal)
    setTimeout(() => killTree(child.pid), GRACE_MS).unref()
  }
  for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(signal, stop)
  watchStack(() => {
    killTree(child.pid)
    process.exit(1)
  })
  child.on('exit', (code, signal) => process.exit(code ?? (signal ? 1 : 0)))
  return child
}
