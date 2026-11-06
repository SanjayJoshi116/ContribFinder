import assert from 'node:assert/strict'
import { test } from 'node:test'

import { matchStack, parsePs } from './stack.mjs'

const REPO = 'c:\\work\\contribfinder'
const SELF = 1

const node = (pid, cmd) => ({ pid, name: 'node', cmd })
const record = (pid, name, exe = 'node', marker = `scripts/${name}.mjs`) => ({
  file: `${name}-${pid}.json`,
  pid,
  exe,
  marker,
})
const killed = (result) => result.kill.map(({ pid }) => pid).sort()

test("another project's identically named runner is left alone", () => {
  const processes = [node(10, 'node scripts/start.mjs'), node(11, 'node scripts\\backend.mjs')]
  const result = matchStack(processes, [record(10, 'start')], REPO, SELF)
  assert.deepEqual(killed(result), [10])
  assert.deepEqual(result.remove, ['start-10.json'])
})

test('a reused pid is not stopped and its record is stale', () => {
  const processes = [
    node(20, 'node C:\\other\\server.js'),
    { pid: 21, name: 'chrome', cmd: 'chrome.exe scripts/worker.mjs' },
  ]
  const records = [record(20, 'backend'), record(21, 'worker'), record(22, 'beat')]
  const result = matchStack(processes, records, REPO, SELF)
  assert.deepEqual(killed(result), [])
  assert.deepEqual(result.remove, ['backend-20.json', 'worker-21.json', 'beat-22.json'])
})

test('the WSL keep-alive is stopped by its record only', () => {
  const keepAlive = { pid: 30, name: 'wsl', cmd: 'wsl.exe -d Ubuntu -- sleep infinity' }
  const other = { pid: 31, name: 'wsl', cmd: 'wsl.exe -d Ubuntu -- sleep infinity' }
  const result = matchStack(
    [keepAlive, other],
    [record(30, 'redis', 'wsl', 'sleep infinity')],
    REPO,
    SELF,
  )
  assert.deepEqual(killed(result), [30])
})

test("this repository's Django, Celery and Vite match by path", () => {
  const processes = [
    { pid: 40, name: 'python', cmd: `python ${REPO}\\apps\\backend\\manage.py runserver 8000` },
    {
      pid: 41,
      name: 'celery',
      cmd: `${REPO}\\apps\\backend\\.venv\\scripts\\celery -A config worker`,
    },
    node(42, `node ${REPO}\\apps\\frontend\\node_modules\\vite\\bin\\vite.js`),
    { pid: 43, name: 'python', cmd: 'python c:\\other\\manage.py runserver' },
    { pid: 44, name: 'code', cmd: `code ${REPO}\\apps\\backend\\manage.py runserver` },
  ]
  assert.deepEqual(killed(matchStack(processes, [], REPO, SELF)), [40, 41, 42])
})

test('never stops the stopping process', () => {
  const result = matchStack(
    [node(SELF, 'node scripts/start.mjs')],
    [record(SELF, 'start')],
    REPO,
    SELF,
  )
  assert.deepEqual(killed(result), [])
})

test('a runner started with a Windows path still matches its record', () => {
  const processes = [node(50, String.raw`node scripts\backend.mjs`)]
  const result = matchStack(processes, [record(50, 'backend')], REPO, SELF)
  assert.deepEqual(killed(result), [50])
})

test('ps output is named by the started executable, not its thread name', () => {
  const out = [
    '  101 /usr/local/bin/node /work/contribfinder/scripts/start.mjs',
    '  102 /work/contribfinder/apps/backend/.venv/bin/python manage.py runserver',
    '',
    '  103 sleep infinity',
  ].join('\n')
  assert.deepEqual(
    parsePs(out).map(({ pid, name }) => [pid, name]),
    [
      [101, 'node'],
      [102, 'python'],
      [103, 'sleep'],
    ],
  )
  assert.equal(parsePs(out)[0].cmd, '/usr/local/bin/node /work/contribfinder/scripts/start.mjs')
})

test('an executable path with spaces is named by its exe link', () => {
  const out = '  201 /home/a b/.nvm/bin/node /work/contribfinder/scripts/start.mjs'
  const exeOf = (pid) => (pid === 201 ? '/home/a b/.nvm/bin/node' : null)
  assert.equal(parsePs(out, exeOf)[0].name, 'node')
  assert.equal(parsePs(out)[0].name, 'a') // without the link only the first word is known
})

test('a sibling checkout whose name starts with this one is not this repository', () => {
  const sibling = `${REPO}-v2`
  const processes = [
    { pid: 60, name: 'python', cmd: `python ${sibling}\\apps\\backend\\manage.py runserver 8000` },
    node(61, `node ${sibling}\\apps\\frontend\\node_modules\\vite\\bin\\vite.js`),
  ]
  assert.deepEqual(killed(matchStack(processes, [], REPO, SELF)), [])
})

test('test runners and other programs are not the stack, whatever their paths', () => {
  const processes = [
    node(70, `node ${REPO}\\apps\\frontend\\node_modules\\vitest\\vitest.mjs run`),
    {
      pid: 71,
      name: 'python',
      cmd: `python -m pytest ${REPO}\\apps\\backend\\tests\\test_celery_config.py`,
    },
    { pid: 74, name: 'python', cmd: `python -m pytest ${REPO}\\apps\\backend\\tests -k celery` },
    {
      pid: 75,
      name: 'python3',
      cmd: `${REPO}/apps/backend/.venv/bin/python3 ${REPO}/apps/backend/.venv/bin/celery -A config worker`,
    },
    { pid: 76, name: 'python', cmd: `python -u -m celery -A config beat --workdir ${REPO}\\apps` },
    { pid: 72, name: 'python', cmd: `python -m celery -A config worker --workdir ${REPO}\\apps` },
    { pid: 73, name: 'celery', cmd: `"${REPO}\\apps\\backend\\.venv\\scripts\\celery.exe" beat` },
  ]
  assert.deepEqual(killed(matchStack(processes, [], REPO, SELF)), [72, 73, 75, 76])
})

test('a recorded process whose command line cannot be read is left running, record kept', () => {
  const processes = [
    { pid: 80, name: 'node', cmd: null },
    { pid: 81, name: 'python', cmd: null },
  ]
  const result = matchStack(processes, [record(80, 'backend')], REPO, SELF)
  assert.deepEqual(killed(result), [])
  assert.deepEqual(result.remove, [])
  assert.deepEqual(
    result.unknown.map(({ pid }) => pid),
    [80],
  )
})

test('a reused pid that cannot be read is another program: its record is stale', () => {
  const processes = [{ pid: 90, name: 'svchost', cmd: null }]
  const result = matchStack(processes, [record(90, 'backend')], REPO, SELF)
  assert.deepEqual(result.unknown, [])
  assert.deepEqual(result.remove, ['backend-90.json'])
})
