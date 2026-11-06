// `npm run start:backend`: apply migrations, then run the Django dev server on :8000.
import path from 'node:path'

import { recordProcess, runChild } from './child.mjs'
import { root } from './env.mjs'
import { uv, uvCommand } from './uv.mjs'

recordProcess()
const backend = path.join(root, 'apps', 'backend')

uv(['run', 'python', 'manage.py', 'migrate', '--noinput'], { cwd: backend })

const [cmd, prefix] = uvCommand()
runChild(cmd, [...prefix, 'run', 'python', 'manage.py', 'runserver', '8000'], { cwd: backend })
