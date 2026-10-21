import path from 'node:path'

/** Session ids of the seeded users, written by the backend server's seed step
 * (scripts/e2e-backend.mjs). */
export const SESSIONS_FILE = path.join(import.meta.dirname, '.sessions.json')
