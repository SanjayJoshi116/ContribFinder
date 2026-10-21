// Which running processes belong to this repository's local stack (`npm run stop`). Pure: the
// process list and the runner records come in, so tests need no real processes.

/** A record still describes ``proc``: same executable, and its marker (the runner's script, or
 * `sleep infinity` for the WSL keep-alive) in the command line. A reused pid of another program
 * never matches. */
function recordMatches({ exe, marker }, proc) {
  if (!marker || proc.name !== exe) return false
  return proc.cmd.replaceAll('\\', '/').toLowerCase().includes(marker.toLowerCase())
}

/** This repository's Django, Celery and Vite: their command lines carry the repository path.
 * Matched by executable, never by text alone: a shell or editor whose command line merely
 * mentions these must survive. */
function ownedByPath({ name, cmd }, repo) {
  const lower = cmd.toLowerCase()
  if (!lower.includes(repo)) return false
  if (name === 'node') return lower.includes('vite')
  if (/^(python\d*(\.\d+)?|celery)$/.test(name)) {
    return /celery|manage\.py"?\s+runserver/.test(lower)
  }
  return false
}

/**
 * @param {{pid: number, name: string, cmd: string}[]} processes live processes (name lowercase,
 *   without `.exe`)
 * @param {{file: string, pid?: number, exe?: string, marker?: string}[]} records runner records
 * @param {string} repo repository root, lowercase
 * @param {number} selfPid the stopping process, never matched
 * @returns {{kill: typeof processes, remove: string[]}} processes to stop, and record files to
 *   delete: those of matched processes (a force-killed runner never runs its exit hook) and
 *   stale ones, whose process is gone or is no longer ours
 */
export function matchStack(processes, records, repo, selfPid) {
  const byPid = new Map(processes.map((proc) => [proc.pid, proc]))
  const kill = new Map()
  const remove = []
  for (const record of records) {
    const proc = byPid.get(record.pid)
    if (proc?.pid === selfPid) continue
    if (proc && recordMatches(record, proc)) kill.set(proc.pid, proc)
    remove.push(record.file)
  }
  for (const proc of processes) {
    if (proc.pid !== selfPid && ownedByPath(proc, repo)) kill.set(proc.pid, proc)
  }
  return { kill: [...kill.values()], remove }
}
