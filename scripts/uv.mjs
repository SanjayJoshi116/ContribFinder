// Runs `uv` whether it is on PATH or only installed as a Python module (`python -m uv`).
import { spawnSync } from 'node:child_process'

const candidates = [
  ['uv', []],
  ['python', ['-m', 'uv']],
  ['python3', ['-m', 'uv']],
  ['py', ['-m', 'uv']],
]

let resolved
export function uvCommand() {
  if (resolved) return resolved
  for (const [cmd, prefix] of candidates) {
    const probe = spawnSync(cmd, [...prefix, '--version'], { stdio: 'ignore', shell: false })
    if (probe.status === 0) return (resolved = [cmd, prefix])
  }
  throw new Error(
    'uv not found. Install it: https://docs.astral.sh/uv/ (or `python -m pip install uv`).',
  )
}

/** Run a uv subcommand in apps/backend; exits the process on failure. */
export function uv(args, { cwd } = {}) {
  const [cmd, prefix] = uvCommand()
  const result = spawnSync(cmd, [...prefix, ...args], { cwd, stdio: 'inherit', shell: false })
  if (result.status !== 0) process.exit(result.status ?? 1)
}
