// `npm run stop`: kill a local stack left running (e.g. a closed terminal or an earlier runner
// that orphaned Celery). Matches only this repository's processes: the runners and WSL
// keep-alive it recorded (.run/, scripts/child.mjs), and its virtualenv (Django, Celery) and
// Vite by path. The redis-server service in WSL is left running; the distro may then idle out.
import { execFileSync } from 'node:child_process'
import { readlinkSync } from 'node:fs'

import { killTree, readRecords, removeRecord } from './child.mjs'
import { root } from './env.mjs'
import { matchStack, parsePs } from './stack.mjs'

function processes() {
  if (process.platform === 'win32') {
    const script =
      // Every process, also those whose command line cannot be read (another user's, or one
      // started elevated): their records must not look stale (SCR-3).
      'Get-CimInstance Win32_Process | ' +
      'Select-Object ProcessId, Name, CommandLine | ConvertTo-Json -Compress'
    const out = execFileSync('powershell.exe', ['-NoProfile', '-Command', script], {
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
    })
    const rows = JSON.parse(out || '[]')
    return (Array.isArray(rows) ? rows : [rows]).map((r) => ({
      pid: r.ProcessId,
      name: r.Name.toLowerCase().replace(/\.exe$/, ''),
      cmd: r.CommandLine ?? null,
    }))
  }
  const out = execFileSync('ps', ['-eo', 'pid=,args='], { encoding: 'utf8' })
  return parsePs(out, (pid) => {
    try {
      return readlinkSync(`/proc/${pid}/exe`) // Linux; macOS has no /proc
    } catch {
      return null
    }
  })
}

// Records first: a runner that starts in between then has a listed process, so its record is
// never mistaken for a stale one.
const records = readRecords()
const { kill: ours, remove, unknown } = matchStack(processes(), records, root, process.pid)

for (const { pid, name } of unknown) {
  console.log(
    `Could not check ${pid} (${name}): its command line is not readable (started elevated?); ` +
      'left running.',
  )
}
if (ours.length === 0 && unknown.length === 0) console.log('Nothing to stop.')
for (const { pid, cmd } of ours) console.log(`Stopping ${pid}: ${cmd.slice(0, 100)}`)
killTree(ours.map(({ pid }) => pid))
for (const file of remove) removeRecord(file)
