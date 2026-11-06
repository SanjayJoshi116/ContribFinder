// Which running processes belong to this repository's local stack (`npm run stop`). Pure: the
// process list and the runner records come in, so tests need no real processes.

import { refuseRun } from './env.mjs'

/** Parses `ps -eo pid=,args=` output. The name is the basename of the executable, lowercase:
 * `exeOf(pid)` (Linux: the `/proc/<pid>/exe` link, exact even with spaces in the path) when it
 * answers, else the first argument. Never `comm`: it can be a thread name (a newer Node reports
 * `MainThread`). */
export function parsePs(out, exeOf = () => null) {
  return out
    .split('\n')
    .map((line) => line.trim().match(/^(\d+)\s+(.*)$/))
    .filter(Boolean)
    .map(([, pid, cmd]) => {
      const exe = exeOf(Number(pid)) ?? cmd.split(/\s/)[0]
      return { pid: Number(pid), name: exe.split('/').pop().toLowerCase(), cmd }
    })
}

/** A record still describes ``proc``: same executable, and its marker (the runner's script, or
 * `sleep infinity` for the WSL keep-alive) in the command line. A reused pid of another program
 * never matches. */
function recordMatches({ exe, marker }, proc) {
  if (!marker || proc.name !== exe) return false
  return normalize(proc.cmd).includes(marker.toLowerCase())
}

/** A path or command line with `/` separators, lowercase, for comparisons on every platform. */
function normalize(text) {
  return text.replaceAll('\\', '/').toLowerCase()
}

// The stack's own programs, in a normalized command line (SCR-2): Vite's own launcher (never
// Vitest's); Django's development server; Celery below.
const VITE = /\/node_modules\/vite\/bin\/vite\.js\b/
const RUNSERVER = /manage\.py"?\s+runserver/

/** Last path part of a command-line token, without quotes or `.exe`. */
const base = (token = '') =>
  token
    .replaceAll('"', '')
    .split('/')
    .pop()
    .replace(/\.exe$/, '')

/** Celery as the program (SCR-2, CR3-4): the command itself (`.../celery`, `celery.exe`), or
 * what python runs (`python .../celery`, `python -m celery`, past interpreter flags). Never an
 * argument that merely is or contains the word (`pytest -k celery`). */
function isCelery(line) {
  const tokens = line.match(/"[^"]*"|\S+/g) ?? []
  if (base(tokens[0]) === 'celery') return true
  if (!/^python\d*(\.\d+)?$/.test(base(tokens[0]))) return false
  let i = 1
  while (tokens[i]?.startsWith('-') && tokens[i] !== '-m') i++
  return tokens[i] === '-m' ? tokens[i + 1] === 'celery' : base(tokens[i]) === 'celery'
}

/** This repository's Django, Celery and Vite: their command lines carry the repository folder.
 * Matched by executable and program shape, never by text alone: a shell, editor or test runner
 * whose command line merely mentions these must survive. ``folder`` is the normalized root with
 * a trailing `/`, so a sibling whose name starts with this one's never matches (SCR-1). */
function ownedByPath({ name, cmd }, folder) {
  if (cmd === null) return false
  const line = normalize(cmd)
  if (!line.includes(folder)) return false
  if (name === 'node') return VITE.test(line)
  if (/^(python\d*(\.\d+)?|celery)$/.test(name)) return isCelery(line) || RUNSERVER.test(line)
  return false
}

/**
 * @param {{pid: number, name: string, cmd: string | null}[]} processes live processes (name
 *   lowercase, without `.exe`; `cmd` null when the command line cannot be read)
 * @param {{file: string, pid?: number, exe?: string, marker?: string}[]} records runner records
 * @param {string} repo repository root (any case, either separator)
 * @param {number} selfPid the stopping process, never matched
 * @returns {{kill: typeof processes, remove: string[], unknown: typeof processes}} processes to
 *   stop; record files to delete: those of matched processes (a force-killed runner never runs
 *   its exit hook) and stale ones, whose process is gone or is no longer ours; and recorded
 *   processes that are alive with the recorded executable but cannot be read (left running,
 *   records kept: SCR-3)
 */
export function matchStack(processes, records, repo, selfPid) {
  const folder = normalize(repo).replace(/\/*$/, '/')
  const byPid = new Map(processes.map((proc) => [proc.pid, proc]))
  const kill = new Map()
  const remove = []
  const unknown = []
  for (const record of records) {
    const proc = byPid.get(record.pid)
    if (proc?.pid === selfPid) continue
    if (proc?.cmd === null && proc.name === record.exe) {
      unknown.push(proc)
      continue
    }
    if (proc && recordMatches(record, proc)) kill.set(proc.pid, proc)
    remove.push(record.file)
  }
  for (const proc of processes) {
    if (proc.pid !== selfPid && ownedByPath(proc, folder)) kill.set(proc.pid, proc)
  }
  return { kill: [...kill.values()], remove, unknown }
}

refuseRun(import.meta.url)
