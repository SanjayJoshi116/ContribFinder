// Loads the repo-root .env into process.env (existing variables win), like django-environ does.
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

export function loadEnv() {
  const file = path.join(root, '.env')
  if (existsSync(file)) process.loadEnvFile(file)
}

/** Host/port of REDIS_URL, or null when Redis is not configured. */
export function redisTarget() {
  const value = process.env.REDIS_URL?.trim()
  if (!value) return null
  const url = new URL(value)
  // Node resolves "localhost" to ::1 first; WSL forwarding and redis bind 127.0.0.1.
  const host = url.hostname === 'localhost' ? '127.0.0.1' : url.hostname
  return { host, port: Number(url.port || 6379), isLocal: ['127.0.0.1', '::1'].includes(host) }
}
