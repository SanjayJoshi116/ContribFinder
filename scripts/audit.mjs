// Audits every locked dependency set for known vulnerabilities (`npm run audit:deps`, CI):
// apps/backend/uv.lock with pip-audit, apps/frontend and the root package-lock.json with npm audit.
// Exit 0 clean, 1 unaccepted findings, 2 an audit could not run or audit-accepted.json is invalid.
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { isMain, root } from './env.mjs'
import { uvCommand } from './uv.mjs'

export const ACCEPTED_FILE = 'audit-accepted.json'
const PIP_AUDIT = 'pip-audit==2.10.1'
const ECOSYSTEMS = new Set(['pypi', 'npm'])
const FIELDS = ['ecosystem', 'id', 'package', 'reason', 'accepted_on']
// npm advisories at these severities fail; lower ones are reported only. Every Python
// advisory fails (pip-audit reports no severity).
const FAILING_NPM = new Set(['high', 'critical'])

/** Errors in the accepted-advisory list; an empty list means it is valid. Strict, so a typo
 * never accepts an advisory silently. */
export function validateAccepted(entries) {
  if (!Array.isArray(entries)) return [`${ACCEPTED_FILE} must be a JSON list`]
  const errors = []
  const seen = new Set()
  entries.forEach((entry, index) => {
    const where = `${ACCEPTED_FILE}[${index}]`
    if (typeof entry !== 'object' || entry === null || Array.isArray(entry)) {
      errors.push(`${where}: must be an object`)
      return
    }
    for (const field of FIELDS) {
      if (typeof entry[field] !== 'string' || !entry[field].trim()) {
        errors.push(`${where}: ${field} must be a non-empty string`)
      }
    }
    for (const field of Object.keys(entry)) {
      if (!FIELDS.includes(field)) errors.push(`${where}: unknown field ${field}`)
    }
    if (typeof entry.ecosystem === 'string' && !ECOSYSTEMS.has(entry.ecosystem)) {
      errors.push(`${where}: ecosystem must be pypi or npm`)
    }
    if (typeof entry.accepted_on === 'string' && !isIsoDate(entry.accepted_on)) {
      errors.push(`${where}: accepted_on must be a date (YYYY-MM-DD)`)
    }
    const key = `${entry.ecosystem}:${entry.id}`
    if (seen.has(key)) errors.push(`${where}: ${entry.id} is accepted twice`)
    seen.add(key)
  })
  return errors
}

function isIsoDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`))
}

// PyPI names compare normalized (PEP 503); npm names exactly.
const normalize = (ecosystem, name) =>
  ecosystem === 'pypi' ? name.toLowerCase().replace(/[-_.]+/g, '-') : name

function acceptance(accepted, ecosystem, pkg, ids) {
  return (
    accepted.find(
      (entry) =>
        entry.ecosystem === ecosystem &&
        normalize(ecosystem, entry.package) === normalize(ecosystem, pkg) &&
        ids.includes(entry.id),
    ) ?? null
  )
}

/** Findings from a `pip-audit --format json` report: one per (package, advisory). */
export function pythonFindings(report, accepted, where = 'apps/backend') {
  if (!Array.isArray(report?.dependencies)) {
    throw new Error('pip-audit report has no dependencies list')
  }
  const findings = []
  const seen = new Set()
  for (const dep of report.dependencies) {
    if (typeof dep?.name !== 'string' || !Array.isArray(dep.vulns ?? [])) {
      throw new Error('pip-audit report has an unexpected dependency entry')
    }
    if (dep.skip_reason) {
      // Not checked is not clean: a skipped package fails until it can be audited.
      findings.push({
        ...base('pypi', where, dep.name, dep.version),
        skipped: dep.skip_reason,
        fails: true,
        accepted: null,
      })
      continue
    }
    for (const vuln of dep.vulns ?? []) {
      const key = `${dep.name}:${vuln.id}`
      if (seen.has(key)) continue // pip-audit repeats an advisory once per fixed version
      seen.add(key)
      const ids = [vuln.id, ...(vuln.aliases ?? [])]
      findings.push({
        ...base('pypi', where, dep.name, dep.version),
        id: vuln.id,
        aliases: vuln.aliases ?? [],
        severity: null,
        fails: true,
        accepted: acceptance(accepted, 'pypi', dep.name, ids),
      })
    }
  }
  return findings
}

/** Findings from an `npm audit --json` report (format 2): one per (package, advisory). */
export function npmFindings(report, accepted, where) {
  if (report?.error) throw new Error(`npm audit: ${report.error.summary ?? report.error.code}`)
  if (report?.auditReportVersion !== 2 || typeof report.vulnerabilities !== 'object') {
    throw new Error('npm audit report is not format 2')
  }
  const findings = []
  const seen = new Set()
  for (const vuln of Object.values(report.vulnerabilities)) {
    for (const via of vuln?.via ?? []) {
      if (typeof via === 'string') continue // a dependency path; its advisory has its own entry
      if (typeof via?.name !== 'string' || typeof via.severity !== 'string') {
        throw new Error('npm audit report has an unexpected advisory entry')
      }
      const id = String(via.url ?? '').match(/GHSA-[\w-]+$/)?.[0] ?? String(via.source)
      const key = `${via.name}:${id}`
      if (seen.has(key)) continue
      seen.add(key)
      findings.push({
        ...base('npm', where, via.name, via.range ?? ''),
        id,
        aliases: [],
        severity: via.severity,
        fails: FAILING_NPM.has(via.severity),
        accepted: acceptance(accepted, 'npm', via.name, [id]),
      })
    }
  }
  return findings
}

const base = (ecosystem, where, pkg, version) => ({ ecosystem, where, package: pkg, version })

/** Accepted entries that matched no finding: fixed meanwhile, so they can be removed. */
export function unusedAccepted(accepted, findings) {
  const used = new Set(findings.map((f) => f.accepted).filter(Boolean))
  return accepted.filter((entry) => !used.has(entry))
}

/** Findings that fail the audit. */
export const failing = (findings) => findings.filter((f) => f.fails && !f.accepted)

export function describe(finding) {
  const what = `${finding.ecosystem} ${finding.where}: ${finding.package} ${finding.version}`
  if (finding.skipped) return `FAIL skipped ${what} (${finding.skipped})`
  const severity = finding.severity ? ` ${finding.severity}` : ''
  const label = finding.accepted
    ? `accepted (${finding.accepted.accepted_on}: ${finding.accepted.reason})`
    : finding.fails
      ? 'FAIL'
      : 'reported only'
  return `${label} ${what} ${finding.id}${severity}`
}

/** The exported requirements without environment markers. pip-audit drops a requirement whose
 * marker is false on the machine running it, so a Windows-only package would never be audited
 * on Linux CI; this way every locked package is audited wherever the audit runs. */
export function withoutMarkers(requirements) {
  return requirements
    .split('\n')
    .map((line) => (/^[A-Za-z0-9]/.test(line) ? line.replace(/\s*;[^\\]*?(\s*\\)?$/, '$1') : line))
    .join('\n')
}

// --- runner -------------------------------------------------------------------------------

class AuditError extends Error {}

function run(cmd, args, cwd) {
  // npm is a .cmd shim on Windows, which only starts through a shell; the arguments are fixed.
  const shell = process.platform === 'win32' && cmd === 'npm'
  const result = spawnSync(cmd, args, { cwd, encoding: 'utf8', shell, maxBuffer: 64 << 20 })
  if (result.error) throw new AuditError(`${cmd} could not start: ${result.error.message}`)
  return result
}

function parseJson(text, what) {
  try {
    return JSON.parse(text)
  } catch {
    throw new AuditError(`${what} did not print a JSON report`)
  }
}

function auditPython(accepted) {
  const cwd = path.join(root, 'apps', 'backend')
  let uv, prefix
  try {
    ;[uv, prefix] = uvCommand()
  } catch (error) {
    throw new AuditError(error.message) // uv.mjs's install advice, without a stack
  }
  const dir = mkdtempSync(path.join(os.tmpdir(), 'contribfinder-audit-'))
  try {
    const requirements = path.join(dir, 'requirements.txt')
    // The lockfile's exact versions with hashes; --disable-pip then audits them unresolved.
    const exported = run(
      uv,
      [
        ...prefix,
        ...['export', '--frozen', '--format', 'requirements-txt', '--no-emit-project'],
        ...['--quiet', '-o', requirements],
      ],
      cwd,
    )
    if (exported.status !== 0) throw new AuditError(`uv export failed:\n${exported.stderr}`)
    writeFileSync(requirements, withoutMarkers(readFileSync(requirements, 'utf8')))
    const audit = run(
      uv,
      [
        ...prefix,
        ...['tool', 'run', PIP_AUDIT, '--requirement', requirements, '--disable-pip'],
        ...['--format', 'json', '--progress-spinner', 'off'],
      ],
      cwd,
    )
    // pip-audit exits 1 when it finds something; anything else without a report is an error.
    if (![0, 1].includes(audit.status)) throw new AuditError(`pip-audit failed:\n${audit.stderr}`)
    return asAuditError(() => pythonFindings(parseJson(audit.stdout, 'pip-audit'), accepted))
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

function auditNpm(dir, accepted) {
  const where = dir === '.' ? 'root' : dir
  const result = run('npm', ['audit', '--json'], path.join(root, dir))
  const report = parseJson(result.stdout, `npm audit in ${where}`)
  return asAuditError(() => npmFindings(report, accepted, where))
}

/** A malformed report is an audit that could not run: its message, without a stack. */
function asAuditError(parse) {
  try {
    return parse()
  } catch (error) {
    throw error instanceof AuditError ? error : new AuditError(error.message)
  }
}

if (isMain(import.meta.url)) {
  try {
    const accepted = parseJson(readFileSync(path.join(root, ACCEPTED_FILE), 'utf8'), ACCEPTED_FILE)
    const errors = validateAccepted(accepted)
    if (errors.length) throw new AuditError(errors.join('\n'))

    const findings = [
      ...auditPython(accepted),
      ...auditNpm('apps/frontend', accepted),
      ...auditNpm('.', accepted),
    ]
    for (const finding of findings) console.log(describe(finding))
    for (const entry of unusedAccepted(accepted, findings)) {
      console.log(
        `unused ${ACCEPTED_FILE} entry: ${entry.ecosystem} ${entry.id} (${entry.package})`,
      )
    }
    const failed = failing(findings)
    console.log(
      failed.length
        ? `${failed.length} unaccepted finding(s); upgrade, or accept in ${ACCEPTED_FILE}.`
        : 'No unaccepted findings.',
    )
    process.exit(failed.length ? 1 : 0)
  } catch (error) {
    // Exit 2, never 1: an audit that did not run must not read as findings, nor pass (uv
    // missing, registry unreachable, a script bug).
    console.error(
      `Audit could not run: ${error instanceof AuditError ? error.message : error.stack}`,
    )
    process.exit(2)
  }
}
