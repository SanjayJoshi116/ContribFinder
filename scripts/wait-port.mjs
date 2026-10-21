// Resolves once host:port accepts TCP connections; rejects after timeoutMs. Each attempt times out
// within the remaining time, so a host that drops packets cannot hold it past the deadline.
// CLI: node scripts/wait-port.mjs <host> <port> [timeoutMs]
import net from 'node:net'

import { isMain } from './env.mjs'

export function waitPort(host, port, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const socket = net.connect({ host, port })
      socket.setTimeout(Math.max(deadline - Date.now(), 1))
      socket.once('timeout', () => socket.destroy(new Error('timeout')))
      socket.once('connect', () => {
        socket.destroy()
        resolve()
      })
      socket.once('error', () => {
        socket.destroy()
        if (Date.now() >= deadline)
          reject(new Error(`${host}:${port} not reachable after ${timeoutMs} ms`))
        else setTimeout(attempt, 500)
      })
    }
    attempt()
  })
}

if (isMain(import.meta.url)) {
  const [host, port, timeout] = process.argv.slice(2)
  waitPort(host, Number(port), timeout ? Number(timeout) : undefined).then(
    () => console.log(`${host}:${port} is up`),
    (error) => {
      console.error(error.message)
      process.exit(1)
    },
  )
}
