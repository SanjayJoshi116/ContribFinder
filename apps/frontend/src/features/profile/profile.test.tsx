import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DeveloperSkill, EvidenceSummary } from '@/api/types'
import { COMPLETED_JOB, ME, SKILLS, SYNCED_USER, json, mockFetch, renderRoute } from '@/test/render'

import { evidenceLabel, groupByCategory } from './evidence'
import { languageRows } from './languages'

const ME_ROUTE = { 'GET /api/v1/auth/me': () => json(ME) }

afterEach(() => {
  vi.unstubAllGlobals()
})

function summary(bySource: EvidenceSummary['by_source'], repos = 0): EvidenceSummary {
  return { by_source: bySource, repository_count: repos, last_observed_at: null }
}

describe('evidenceLabel', () => {
  it.each([
    [
      summary({ readme: 1, language: 8, dependency: 2 }, 8),
      '8 repositories · dependencies · README',
    ],
    [summary({ readme: 1 }), 'README'],
    [summary({ topic: 1 }, 1), '1 repository · topics'],
    [
      summary({ pull_request: 2, repeated_contribution: 1, commit: 1 }, 2),
      '2 repositories · repeated contributions · pull requests · recent pushes',
    ],
    [summary({}), ''],
  ])('%o → %s', (input, expected) => {
    expect(evidenceLabel(input)).toBe(expected)
  })
})

describe('groupByCategory', () => {
  it('orders categories and drops empty ones', () => {
    const groups = groupByCategory(SKILLS as DeveloperSkill[])
    expect(groups.map(([category, skills]) => [category, skills.map((s) => s.skill.name)])).toEqual(
      [
        ['language', ['Python']],
        ['framework', ['Django']],
      ],
    )
  })
})

describe('languageRows', () => {
  it('keeps the top 8 and folds the rest into Other', () => {
    const languages = Array.from({ length: 10 }, (_, i) => ({
      name: `L${i}`,
      bytes: 100 - i,
      share: 0.1,
      repo_count: 1,
    }))
    const rows = languageRows(languages)
    expect(rows).toHaveLength(9)
    expect(rows.at(-1)).toEqual({ name: 'Other', share: 0.2 })
  })
})

describe('profile page', () => {
  it('shows summary, skills grouped by category, interests and languages', async () => {
    mockFetch({ ...ME_ROUTE, ...SYNCED_USER })
    renderRoute('/app')

    expect(await screen.findByText(/works mostly in python/i)).toBeInTheDocument()

    const skills = await screen.findByRole('region', { name: 'Skills' })
    const languages = await within(skills).findByRole('list', { name: 'Languages' })
    expect(within(languages).getByText('Python')).toBeInTheDocument()
    expect(
      within(languages).getByText('8 repositories · dependencies · README'),
    ).toBeInTheDocument()
    expect(within(skills).getByRole('list', { name: 'Frameworks' })).toHaveTextContent('Django')
    // Confidence is never printed as a number.
    expect(skills.textContent).not.toMatch(/\d+\s*%|0\.93/)

    const interests = screen.getByRole('list', { name: 'Interests' })
    expect(within(interests).getByText('Developer tooling')).toBeInTheDocument()

    const chart = screen.getByRole('region', { name: 'Languages' })
    expect(await within(chart).findByRole('list', { name: 'Languages' })).toHaveTextContent(
      'Python 70%',
    )

    // Experience level is never shown.
    expect(document.body.textContent).not.toMatch(/beginner|intermediate|experienced/i)
  })

  it('expands a skill to show its evidence with repository links', async () => {
    mockFetch({ ...ME_ROUTE, ...SYNCED_USER })
    renderRoute('/app')

    const toggle = await screen.findByRole('button', { name: /django/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')

    const evidence = screen.getByRole('list', { name: 'Evidence for Django' })
    expect(within(evidence).getByText('Dependency')).toBeInTheDocument()
    expect(within(evidence).getByRole('link', { name: 'octocat/tools' })).toHaveAttribute(
      'href',
      'https://github.com/octocat/tools',
    )
  })

  it('shows a preparing state when the profile is not analyzed yet', async () => {
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/profile': () =>
        json({ error: { code: 'not_analyzed', message: 'Not built yet.' } }, 404),
    })
    renderRoute('/app')

    expect(await screen.findByText(/being prepared/i)).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Repositories' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Skills' })).not.toBeInTheDocument()
  })
})

describe('onboarding analysis failure', () => {
  it('explains that the profile could not be built and offers a retry', async () => {
    mockFetch({
      ...ME_ROUTE,
      'GET /api/v1/sync/status': () =>
        json({
          job: {
            ...COMPLETED_JOB,
            status: 'FAILED',
            error_code: 'analysis_failed',
            steps: { ...COMPLETED_JOB.steps, analysis: 'failed' },
          },
          last_synced_at: null,
        }),
    })
    renderRoute('/onboarding')

    expect(await screen.findByRole('alert')).toHaveTextContent(/profile could not be built/i)
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})
