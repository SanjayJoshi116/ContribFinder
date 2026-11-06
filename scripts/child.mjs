// Run a long-lived child (Django, Celery) and make sure it stops, with everything it started,
// when this runner is stopped. On Windows, Ctrl+C already reaches the child through the shared
// console; killing only the direct child (uv.exe) would orphan celery/python grandchildren, so
// the runner waits for a clean exit and then kills the whole process tree.
import { spawn, spawnSync } from 'node:child_process'
import { mkdirSync, readdirSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'

import { refuseRun, root } from './env.mjs'

const GRACE_MS = 5_000

/** Runner records (gitignored): how `npm run stop` tells this repository's runners from another
 * project's identically named scripts. */
export const RUN_DIR = path.join(root, '.run')

/** This runner's script, relative to the repository (`scripts/backend.mjs`). */
const script = () => path.relative(root, realpathSync(process.argv[1])).replaceAll('\\', '/')

/** Record ``pid`` for `npm run stop`, which stops it only while the live process still has
 * ``exe`` (executable name without `.exe`) and ``marker`` in its command line. Defaults describe
 * the calling runner itself. The record goes when this runner exits; one left by a killed
 * runner is stale and pruned. */
export function recordProcess({ pid = process.pid, exe = 'node', marker = script() } = {}) {
  mkdirSync(RUN_DIR, { recursive: true })
  const name = path.basename(process.argv[1], '.mjs')
  const file = path.join(RUN_DIR, `${name}-${pid}.json`)
  writeFileSync(file, JSON.stringify({ pid, exe, marker, startedAt: new Date().toISOString() }))
  process.on('exit', () => removeRecord(file))
  return file
}

/** All records, each with its ``file``; an unreadable one has no ``pid`` (so it is stale). */
export function readRecords(dir = RUN_DIR) {
  let names
  try {
    names = readdirSync(dir)
  } catch {
    return []
  }
  return names
    .filter((name) => name.endsWith('.json'))
    .map((name) => {
      const file = path.join(dir, name)
      try {
        return { file, ...JSON.parse(readFileSync(file, 'utf8')) }
      } catch {
        return { file }
      }
    })
}

export function removeRecord(file) {
  rmSync(file, { force: true })
}

/** Drop records whose process is gone (a runner killed before its exit hook ran). */
export function pruneRecords(dir = RUN_DIR) {
  for (const { file, pid } of readRecords(dir)) if (!pid || !alive(pid)) removeRecord(file)
}

/** ``roots`` and all their descendants, from ``[pid, ppid]`` pairs. */
export function withDescendants(roots, pairs) {
  const children = new Map()
  for (const [pid, ppid] of pairs) children.set(ppid, [...(children.get(ppid) ?? []), pid])
  const found = new Set(roots)
  for (const pid of found) for (const child of children.get(pid) ?? []) found.add(child)
  return [...found]
}

/** ``[pid, ppid]`` pairs of every process (`ps -eo pid=,ppid=`); empty when ps fails. */
function processPairs() {
  const out = spawnSync('ps', ['-eo', 'pid=,ppid='], { encoding: 'utf8' }).stdout ?? ''
  return out
    .split('\n')
    .map((line) => line.trim().split(/\s+/).map(Number))
    .filter(([pid, ppid]) => Number.isInteger(pid) && Number.isInteger(ppid))
}

/** Force-kill processes (one pid or an array) and all their descendants. */
export function killTree(pidOrPids) {
  const pids = [pidOrPids].flat().filter((pid) => pid !== undefined)
  if (pids.length === 0) return
  if (process.platform === 'win32') {
    // One taskkill for all: it goes on past pids that are already gone (killed with a parent).
    const args = pids.flatMap((pid) => ['/pid', String(pid)])
    spawnSync('taskkill', [...args, '/T', '/F'], { stdio: 'ignore' })
    return
  }
  // POSIX: the tree is listed before anything dies (an orphan's parent link is lost), then
  // each group a pid leads (a detached runner child) and every listed descendant is killed. A
  // pid that leads no group (a non-detached child, a path-matched Celery) is reached through
  // the tree (CR3-3, CR3-5).
  const tree = withDescendants(pids, processPairs())
  for (const pid of pids) sigkill(-pid)
  for (const pid of tree) sigkill(pid)
}

function sigkill(target) {
  try {
    process.kill(target, 'SIGKILL')
  } catch {
    // already gone, or no such group
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
  // On POSIX a detached child leads its own process group and is signalled through it; one
  // started with `detached: false` (e2e-backend.mjs) leads none, so it is signalled itself
  // (SCR-4). A force kill takes the whole tree either way (`killTree`).
  const grouped = posix && (options.detached ?? true)
  const forceKill = () => killTree(child.pid)
  let stopping = false
  const stop = (signal) => {
    if (stopping) {
      forceKill()
      return
    }
    stopping = true
    try {
      if (grouped) process.kill(-child.pid, signal)
      else if (posix) child.kill(signal)
    } catch {
      // already exited
    }
    setTimeout(forceKill, GRACE_MS).unref()
  }
  for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(signal, stop)
  watchStack(() => {
    forceKill()
    process.exit(1)
  })
  child.on('error', (error) => {
    console.error(`Could not start ${cmd}: ${error.message}`)
    process.exit(1)
  })
  child.on('exit', (code, signal) => process.exit(code ?? (signal ? 1 : 0)))
  return child
}

refuseRun(import.meta.url)
