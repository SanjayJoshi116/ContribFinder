// `npm run start:backend`: apply migrations, then run the Django dev server on :8000.
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { recordProcess, runChild } from './child.mjs'
import { uv, uvCommand } from './uv.mjs'

recordProcess()
const backend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'apps', 'backend')

uv(['run', 'python', 'manage.py', 'migrate', '--noinput'], { cwd: backend })

const [cmd, prefix] = uvCommand()
runChild(cmd, [...prefix, 'run', 'python', 'manage.py', 'runserver', '8000'], { cwd: backend })
