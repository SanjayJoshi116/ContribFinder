import type {
  DeveloperInterest,
  DeveloperSkill,
  EvidenceSummary,
  SkillCategory,
  SkillSource,
} from '@/api/types'

/** Heading and singular noun per category, in display order. A `Record` over the generated
 * enum, so a new category cannot be left out (its skills would not be shown). */
const CATEGORIES: Record<SkillCategory, { label: string; noun: string }> = {
  language: { label: 'Languages', noun: 'Language' },
  framework: { label: 'Frameworks', noun: 'Framework' },
  library: { label: 'Libraries', noun: 'Library' },
  database: { label: 'Databases', noun: 'Database' },
  cloud: { label: 'Cloud', noun: 'Cloud' },
  devops: { label: 'DevOps', noun: 'DevOps' },
  tool: { label: 'Tools', noun: 'Tool' },
}

const perCategory = (text: (category: { label: string; noun: string }) => string) =>
  Object.fromEntries(
    Object.entries(CATEGORIES).map(([key, category]) => [key, text(category)]),
  ) as Record<SkillCategory, string>

/** Heading per category, in display order. */
export const CATEGORY_LABELS = perCategory((category) => category.label)

export const CATEGORY_ORDER = Object.keys(CATEGORIES) as SkillCategory[]

/** Accessible name of each category's list: distinct from the languages chart's name. */
export const CATEGORY_LIST_NAMES = perCategory((category) => `${category.noun} skills`)

export const SKILL_SOURCE_LABELS: Record<SkillSource, string> = {
  readme: 'Profile README',
  language: 'Repository language',
  topic: 'Repository topic',
  dependency: 'Dependency',
  commit: 'Recent push',
  pull_request: 'Merged pull request',
  repeated_contribution: 'Repeated contribution',
}

export const INTEREST_SOURCE_LABELS: Record<
  DeveloperInterest['evidence'][number]['source'],
  string
> = {
  readme: 'Profile README',
  repo_description: 'Repository description',
  topic: 'Repository topic',
  contribution: 'Contribution',
}

// Evidence kinds named in the bar label, strongest first. Repository languages are covered
// by the repository count.
const LABEL_PARTS: readonly [SkillSource, string][] = [
  ['repeated_contribution', 'repeated contributions'],
  ['pull_request', 'pull requests'],
  ['commit', 'recent pushes'],
  ['dependency', 'dependencies'],
  ['topic', 'topics'],
  ['readme', 'README'],
]

/** Describes a skill's evidence, e.g. "8 repositories · dependencies · README". Never a
 * percentage: confidence is a ranking signal, not a measure of expertise. Never empty: language
 * evidence whose repository is gone still says so. */
export function evidenceLabel(summary: EvidenceSummary): string {
  const parts: string[] = []
  const repos = summary.repository_count
  if (repos > 0) parts.push(`${repos} ${repos === 1 ? 'repository' : 'repositories'}`)
  for (const [source, label] of LABEL_PARTS) {
    if ((summary.by_source[source] ?? 0) > 0) parts.push(label)
  }
  if (parts.length > 0) return parts.join(' · ')
  return (summary.by_source.language ?? 0) > 0 ? 'repository languages' : 'evidence recorded'
}

/** Skills grouped by category in display order; empty categories are left out. */
export function groupByCategory(
  skills: readonly DeveloperSkill[],
): [SkillCategory, DeveloperSkill[]][] {
  return CATEGORY_ORDER.map(
    (category) =>
      [category, skills.filter((s) => s.skill.category === category)] as [
        SkillCategory,
        DeveloperSkill[],
      ],
  ).filter(([, group]) => group.length > 0)
}
