import type { HtmlTagDescriptor, Plugin } from 'vite'

/** The built SPA's Content Security Policy (spec `web-client`, "Content Security Policy in the
 * built app"). Scripts and API calls stay on this origin; images also allow `data:` and GitHub
 * avatars; inline style attributes are allowed because Recharts and Radix set them.
 * `frame-ancestors` is ignored in a meta tag: whoever serves the build sends this policy as a
 * header with `frame-ancestors 'none'` added (README). The backend's own policies live in
 * `apps/backend/config/settings/base.py`. */
export const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "script-src 'self'",
  "connect-src 'self'",
  "img-src 'self' data: https://avatars.githubusercontent.com",
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'self'",
].join('; ')

const META: HtmlTagDescriptor = {
  tag: 'meta',
  attrs: { 'http-equiv': 'Content-Security-Policy', content: CONTENT_SECURITY_POLICY },
  injectTo: 'head-prepend',
}

/** Writes the policy into the built `index.html` only: the dev server's hot reload injects an
 * inline script, which the policy would block. */
export function contentSecurityPolicy(): Plugin {
  return {
    name: 'contribfinder-content-security-policy',
    apply: 'build',
    transformIndexHtml: () => [META],
  }
}
