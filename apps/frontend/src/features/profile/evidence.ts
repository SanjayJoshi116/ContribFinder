import type { DeveloperSkill, EvidenceSummary, SkillCategory, SkillSource } from '@/api/types'

export const CATEGORY_ORDER: readonly SkillCategory[] = [
  'language',
  'framework',
  'library',
  'database',
  'cloud',
  'devops',
  'tool',
]

export const CATEGORY_LABELS: Record<SkillCategory, string> = {
  language: 'Languages',
  framework: 'Frameworks',
  library: 'Libraries',
  database: 'Databases',
  cloud: 'Cloud',
  devops: 'DevOps',
  tool: 'Tools',
}

export const SOURCE_LABELS: Record<SkillSource, string> = {
  readme: 'Profile README',
  language: 'Repository language',
  topic: 'Repository topic',
  dependency: 'Dependency',
  commit: 'Recent push',
  pull_request: 'Merged pull request',
  repeated_contribution: 'Repeated contribution',
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
 * percentage: confidence is a ranking signal, not a measure of expertise. */
export function evidenceLabel(summary: EvidenceSummary): string {
  const parts: string[] = []
  const repos = summary.repository_count
  if (repos > 0) parts.push(`${repos} ${repos === 1 ? 'repository' : 'repositories'}`)
  for (const [source, label] of LABEL_PARTS) {
    if ((summary.by_source[source] ?? 0) > 0) parts.push(label)
  }
  return parts.join(' · ')
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
