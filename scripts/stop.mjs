// `npm run stop`: kill a local stack left running (e.g. a closed terminal or an earlier runner
// that orphaned Celery). Matches only this repository's processes: its runner scripts, its
// virtualenv (Django, Celery) and its Vite. Redis in WSL is left running.
import { execFileSync } from 'node:child_process'

import { killTree } from './child.mjs'
import { root } from './env.mjs'

const repo = root.toLowerCase()
const runners = /scripts[\\/](start|backend|worker|beat|redis)\.mjs/

function processes() {
  if (process.platform === 'win32') {
    const script =
      'Get-CimInstance Win32_Process | Where-Object CommandLine | ' +
      'Select-Object ProcessId, Name, CommandLine | ConvertTo-Json -Compress'
    const out = execFileSync('powershell.exe', ['-NoProfile', '-Command', script], {
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
    })
    const rows = JSON.parse(out || '[]')
    return (Array.isArray(rows) ? rows : [rows]).map((r) => ({
      pid: r.ProcessId,
      name: r.Name.toLowerCase().replace(/\.exe$/, ''),
      cmd: r.CommandLine,
    }))
  }
  const out = execFileSync('ps', ['-eo', 'pid=,comm=,args='], { encoding: 'utf8' })
  return out
    .split('\n')
    .filter(Boolean)
    .map((line) => {
      const [, pid, name, cmd] = line.trim().match(/^(\d+)\s+(\S+)\s+(.*)$/)
      return { pid: Number(pid), name: name.split('/').pop().toLowerCase(), cmd }
    })
}

// Match by executable, never by text alone: a shell whose command line merely mentions these
// scripts (an editor, this very `npm run stop`) must survive.
const ours = processes().filter(({ pid, name, cmd }) => {
  if (pid === process.pid) return false
  const lower = cmd.toLowerCase()
  if (name === 'node') return runners.test(cmd) || (lower.includes(repo) && lower.includes('vite'))
  if (/^(python\d*(\.\d+)?|celery)$/.test(name)) {
    return lower.includes(repo) && /celery|manage\.py"?\s+runserver/.test(lower)
  }
  return false
})

if (ours.length === 0) {
  console.log('Nothing to stop.')
} else {
  for (const { pid, cmd } of ours) {
    console.log(`Stopping ${pid}: ${cmd.slice(0, 100)}`)
    killTree(pid)
  }
}
