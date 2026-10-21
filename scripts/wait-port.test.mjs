import assert from 'node:assert/strict'
import net from 'node:net'
import { test } from 'node:test'

import { waitPort } from './wait-port.mjs'

test('resolves for a listening port', async () => {
  const server = net.createServer().listen(0, '127.0.0.1')
  await new Promise((resolve) => server.once('listening', resolve))
  try {
    await waitPort('127.0.0.1', server.address().port, 2_000)
  } finally {
    server.close()
  }
})

test('rejects a closed port at the deadline', async () => {
  const server = net.createServer().listen(0, '127.0.0.1')
  await new Promise((resolve) => server.once('listening', resolve))
  const { port } = server.address()
  await new Promise((resolve) => server.close(resolve))
  await assert.rejects(waitPort('127.0.0.1', port, 600), /not reachable after 600 ms/)
})

test('a host that drops packets fails near the deadline, not at the OS connect timeout', async () => {
  // TEST-NET-1 (RFC 5737): never routed, so the connection attempt hangs instead of failing.
  const started = Date.now()
  await assert.rejects(waitPort('192.0.2.1', 6379, 1_000), /not reachable/)
  assert.ok(Date.now() - started < 3_000, `took ${Date.now() - started} ms`)
})
