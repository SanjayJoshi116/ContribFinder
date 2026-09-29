// Runs `uv` whether it is on PATH, installed in a standard location that is not on PATH
// (e.g. `pip install --user uv` on Windows), or only available as `python -m uv`.
// Override with UV_BIN=<path to uv executable>.
import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const exe = process.platform === 'win32' ? 'uv.exe' : 'uv'

/** Absolute paths where installers put uv without necessarily adding it to PATH. */
function knownLocations() {
  const home = os.homedir()
  const dirs = [path.join(home, '.local', 'bin'), path.join(home, '.cargo', 'bin')]
  if (process.platform === 'win32') {
    // pip --user and python.org installs: <root>\PythonXY\Scripts
    for (const root of [
      process.env.APPDATA && path.join(process.env.APPDATA, 'Python'),
      process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Programs', 'Python'),
    ]) {
      if (!root || !existsSync(root)) continue
      for (const entry of readdirSync(root).sort().reverse()) {
        dirs.push(path.join(root, entry, 'Scripts'))
      }
    }
  }
  return dirs.map((dir) => path.join(dir, exe))
}

function candidates() {
  const list = []
  if (process.env.UV_BIN) list.push([process.env.UV_BIN, []])
  list.push(['uv', []])
  for (const file of knownLocations()) if (existsSync(file)) list.push([file, []])
  for (const python of ['python', 'python3', 'py']) list.push([python, ['-m', 'uv']])
  return list
}

let resolved
export function uvCommand() {
  if (resolved) return resolved
  const tried = []
  for (const [cmd, prefix] of candidates()) {
    const probe = spawnSync(cmd, [...prefix, '--version'], { stdio: 'ignore', shell: false })
    if (probe.status === 0) return (resolved = [cmd, prefix])
    tried.push([cmd, ...prefix].join(' '))
  }
  throw new Error(
    'uv not found. Tried:\n  ' +
      tried.join('\n  ') +
      '\nInstall it (https://docs.astral.sh/uv/, or `python -m pip install uv`), add it to PATH, ' +
      'or set UV_BIN to the uv executable.',
  )
}

/** Run a uv subcommand; exits the process on failure. */
export function uv(args, { cwd } = {}) {
  const [cmd, prefix] = uvCommand()
  const result = spawnSync(cmd, [...prefix, ...args], { cwd, stdio: 'inherit', shell: false })
  if (result.status !== 0) process.exit(result.status ?? 1)
}
