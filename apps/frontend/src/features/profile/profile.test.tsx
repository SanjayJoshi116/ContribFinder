import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DeveloperSkill, EvidenceSummary, SkillCategory } from '@/api/types'
import { formatDate } from '@/lib/format'
import {
  COMPLETED_JOB,
  INTERESTS,
  ME,
  SKILLS,
  SYNCED_USER,
  json,
  mockFetch,
  page,
  renderRoute,
} from '@/test/render'

import { interestsKey, skillsKey } from './api'
import { CATEGORY_ORDER, evidenceLabel, groupByCategory } from './evidence'
import { languageRows, percent } from './languages'

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
    // Language evidence whose repository is gone still names its kind; never an empty label.
    [summary({ language: 2 }, 0), 'repository languages'],
    [summary({}), 'evidence recorded'],
  ])('%o → %s', (input, expected) => {
    expect(evidenceLabel(input)).toBe(expected)
  })
})

describe('CATEGORY_ORDER', () => {
  it('lists every category of the API, so no skill is left without a group', () => {
    // Every value of the generated CategoryEnum (src/api/schema.d.ts).
    const all: SkillCategory[] = [
      'language',
      'framework',
      'library',
      'database',
      'cloud',
      'devops',
      'tool',
    ]
    expect([...CATEGORY_ORDER].sort()).toEqual([...all].sort())
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

/** Languages with these byte counts; `share` is rounded as the API does. */
function languages(bytes: number[]) {
  const total = bytes.reduce((sum, b) => sum + b, 0)
  return bytes.map((b, i) => ({
    name: `L${i}`,
    bytes: b,
    share: Math.round((b / total) * 100) / 100,
    repo_count: 1,
  }))
}

describe('languageRows', () => {
  it('keeps the top 8 and folds the rest into Other', () => {
    const rows = languageRows(languages([10, 10, 10, 10, 10, 10, 10, 10, 10, 10]))
    expect(rows).toHaveLength(9)
    expect(rows.at(-1)).toEqual({ name: 'Other', share: 0.2 })
  })

  it('shows 9 languages by name, without Other', () => {
    const rows = languageRows(languages([10, 10, 10, 10, 10, 10, 10, 10, 10]))
    expect(rows).toHaveLength(9)
    expect(rows.map((row) => row.name)).not.toContain('Other')
  })

  it('orders rows by bytes whatever order the API gives', () => {
    const rows = languageRows(languages([1, 5, 3]))
    expect(rows.map((row) => row.name)).toEqual(['L1', 'L2', 'L0'])
  })

  it('counts many small languages in Other from bytes', () => {
    // 8 large languages, then 12 at 0.3% each: the API rounds each of those shares to 0.
    const rows = languageRows(languages([...Array(8).fill(1203), ...Array(12).fill(30)]))
    const other = rows.at(-1)!
    expect(other.name).toBe('Other')
    expect(percent(other.share)).toBe('4%')
    expect(rows.reduce((sum, row) => sum + row.share, 0)).toBeCloseTo(1)
  })
})

describe('percent', () => {
  it.each([
    [0.002, '<1%'],
    [0.005, '1%'],
    [0.73, '73%'],
    [0, '0%'],
  ])('%f → %s', (share, expected) => {
    expect(percent(share)).toBe(expected)
  })
})

describe('profile page', () => {
  it('shows summary, skills grouped by category, interests and languages', async () => {
    mockFetch({ ...ME_ROUTE, ...SYNCED_USER })
    renderRoute('/app')

    expect(await screen.findByText(/works mostly in python/i)).toBeInTheDocument()

    const skills = await screen.findByRole('region', { name: 'Skills' })
    const languages = await within(skills).findByRole('list', { name: 'Language skills' })
    expect(within(languages).getByText('Python')).toBeInTheDocument()
    expect(
      within(languages).getByText('8 repositories · dependencies · README'),
    ).toBeInTheDocument()
    expect(within(skills).getByRole('list', { name: 'Framework skills' })).toHaveTextContent(
      'Django',
    )
    // Confidence is never printed as a number (evidence details, such as "90% of code", are
    // inside the collapsed disclosures, not on the bars).
    for (const bar of within(skills).getAllByRole('listitem')) {
      const summary = bar.querySelector('summary')
      if (summary) expect(summary.textContent).not.toMatch(/\d+\s*%|0\.93/)
    }

    const interests = screen.getByRole('list', { name: 'Interests' })
    expect(within(interests).getByText('Developer tooling')).toBeInTheDocument()

    // Distinct names: no within() needed to tell the skill list from the chart.
    expect(await screen.findByRole('list', { name: 'Languages by code' })).toHaveTextContent(
      'Python 70%',
    )
    expect(screen.getByRole('list', { name: 'Language skills' })).toBeInTheDocument()

    // Experience level is never shown.
    expect(document.body.textContent).not.toMatch(/beginner|intermediate|experienced/i)
  })

  it('expands a skill to show its evidence with repository links', async () => {
    mockFetch({ ...ME_ROUTE, ...SYNCED_USER })
    renderRoute('/app')

    const name = await screen.findByTitle('Django')
    const details = name.closest('details')!
    expect(details).not.toHaveAttribute('open')
    expect(details.querySelector('[aria-controls]')).toBeNull()
    await userEvent.click(name)
    expect(details).toHaveAttribute('open')

    const evidence = screen.getByRole('list', { name: 'Evidence for Django' })
    expect(within(evidence).getByText('Dependency')).toBeInTheDocument()
    expect(within(evidence).getByRole('link', { name: 'octocat/tools' })).toHaveAttribute(
      'href',
      'https://github.com/octocat/tools',
    )
  })

  it('shows when each interest signal was observed', async () => {
    mockFetch({ ...ME_ROUTE, ...SYNCED_USER })
    renderRoute('/app')

    const interests = await screen.findByRole('list', { name: 'Interests' })
    await userEvent.click(within(interests).getByText('Developer tooling'))
    const evidence = screen.getByRole('list', { name: 'Evidence for Developer tooling' })
    expect(evidence).toHaveTextContent('Repository topic')
    expect(evidence).toHaveTextContent(formatDate('2026-09-01T00:00:00Z'))
  })

  it('keeps an expanded skill and interest open when a re-analysis recreates their rows', async () => {
    let reanalyzed = false
    const renumbered = <T extends { id: number }>(rows: T[]) =>
      rows.map((row) => ({ ...row, id: row.id + 100 }))
    mockFetch({
      ...ME_ROUTE,
      ...SYNCED_USER,
      'GET /api/v1/profile/skills?page_size=200': () =>
        page(reanalyzed ? renumbered(SKILLS) : SKILLS),
      'GET /api/v1/profile/interests?page_size=200': () =>
        page(reanalyzed ? renumbered(INTERESTS) : INTERESTS),
    })
    const { queryClient } = renderRoute('/app')
    const skill = (await screen.findByTitle('Django')).closest('details')!
    await userEvent.click(screen.getByTitle('Django'))
    const tooling = () =>
      within(screen.getByRole('list', { name: 'Interests' })).getByText('Developer tooling')
    await userEvent.click(tooling())
    const interest = tooling().closest('details')!

    reanalyzed = true
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: skillsKey })
      await queryClient.refetchQueries({ queryKey: interestsKey })
    })

    await waitFor(() => expect(screen.getByTitle('Django').closest('details')).toBe(skill))
    expect(skill).toHaveAttribute('open')
    expect(tooling().closest('details')).toBe(interest)
    expect(interest).toHaveAttribute('open')
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
