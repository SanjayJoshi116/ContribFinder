// `npm run start:frontend`: the Vite dev server on :5173 (proxies /api to Django). Runs Vite's
// script with node directly: going through npm.cmd adds a "Terminate batch job (Y/N)?" prompt
// on Ctrl+C in Windows consoles.
import path from 'node:path'

import { recordProcess, runChild } from './child.mjs'
import { root } from './env.mjs'

recordProcess()
const frontend = path.join(root, 'apps', 'frontend')
runChild(process.execPath, [path.join(frontend, 'node_modules', 'vite', 'bin', 'vite.js')], {
  cwd: frontend,
})
