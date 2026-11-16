import { readFileSync, existsSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

import { CONTENT_SECURITY_POLICY, contentSecurityPolicy } from './csp.config.ts'

const directives = new Map(
  CONTENT_SECURITY_POLICY.split(';').map((part) => {
    const [name = '', ...values] = part.trim().split(/\s+/)
    return [name, values] as const
  }),
)

describe('content security policy', () => {
  it.each([
    ['script-src', ["'self'"]],
    ['connect-src', ["'self'"]],
    ['object-src', ["'none'"]],
    ['base-uri', ["'none'"]],
    ['img-src', ["'self'", 'data:', 'https://avatars.githubusercontent.com']],
  ])('sets %s', (name, values) => {
    expect(directives.get(name)).toEqual(values)
  })

  it('never allows inline or evaluated scripts', () => {
    expect(directives.get('script-src')).not.toContain("'unsafe-inline'")
    expect(CONTENT_SECURITY_POLICY).not.toContain("'unsafe-eval'")
  })

  it('applies to the build only, as the first tag in <head>', () => {
    const plugin = contentSecurityPolicy()
    expect(plugin.apply).toBe('build')
    const transform = plugin.transformIndexHtml as () => unknown
    expect(transform()).toEqual([
      {
        tag: 'meta',
        attrs: { 'http-equiv': 'Content-Security-Policy', content: CONTENT_SECURITY_POLICY },
        injectTo: 'head-prepend',
      },
    ])
  })

  // After `npm run build`: the written index carries the policy and no inline script.
  const built = path.join(import.meta.dirname, 'dist', 'index.html')
  // CI builds before testing, so there a missing build fails instead of skipping (CI-2).
  it.runIf(existsSync(built) || process.env.CI === 'true')(
    'is in the built index, which has no inline script',
    () => {
      const html = readFileSync(built, 'utf-8')
      expect(html).toContain('http-equiv="Content-Security-Policy"')
      const scripts = html.match(/<script\b[^>]*>/gi) ?? []
      expect(scripts.length).toBeGreaterThan(0)
      expect(scripts.every((tag) => tag.includes('src='))).toBe(true)
    },
  )
})
