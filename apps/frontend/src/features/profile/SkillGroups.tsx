import { ChevronRight } from 'lucide-react'
import { useState } from 'react'

import type { DeveloperSkill } from '@/api/types'

import { EvidenceItem } from './EvidenceItem'
import {
  CATEGORY_LABELS,
  CATEGORY_LIST_NAMES,
  SKILL_SOURCE_LABELS,
  evidenceLabel,
  groupByCategory,
} from './evidence'

/** One skill: a native disclosure (like interests). Keyed by slug, so its open state survives a
 * refetch that recreates the skill rows. The evidence list is built only while open: a skill can
 * have one row per supporting repository. */
function SkillBar({ skill }: { skill: DeveloperSkill }) {
  const [open, setOpen] = useState(false)
  const name = skill.skill.name
  const label = evidenceLabel(skill.evidence_summary)
  // Bar length reflects the strength of evidence; no number is shown (SRS-2 §15).
  const width = `${Math.max(Math.round(skill.confidence * 100), 4)}%`
  return (
    <li>
      <details className="group" onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary className="hover:bg-secondary/60 grid cursor-pointer list-none grid-cols-[1rem_8rem_1fr] items-center gap-3 rounded px-1 py-1 text-left [&::-webkit-details-marker]:hidden">
          <ChevronRight className="size-4 transition-transform group-open:rotate-90" aria-hidden />
          <span className="truncate text-sm font-medium" title={name}>
            {name}
          </span>
          <span className="space-y-1">
            <span className="bg-secondary block h-2 overflow-hidden rounded-full" aria-hidden>
              <span className="bg-primary block h-full rounded-full" style={{ width }} />
            </span>
            <span className="text-muted-foreground block text-xs">{label}</span>
          </span>
        </summary>
        {open && (
          <ul className="mt-2 space-y-1 pl-6 text-sm" aria-label={`Evidence for ${name}`}>
            {skill.evidence.map((item, index) => (
              <EvidenceItem
                key={index}
                label={SKILL_SOURCE_LABELS[item.source]}
                repository={item.repository}
                detail={item.detail}
                observedAt={item.observed_at}
              />
            ))}
          </ul>
        )}
      </details>
    </li>
  )
}

export function SkillGroups({ skills }: { skills: readonly DeveloperSkill[] }) {
  if (skills.length === 0) {
    return <p className="text-muted-foreground text-sm">No skills detected from public data yet.</p>
  }
  return (
    <div className="space-y-5">
      {groupByCategory(skills).map(([category, group]) => (
        <section key={category} className="space-y-1">
          <h3 className="text-muted-foreground text-sm font-medium">{CATEGORY_LABELS[category]}</h3>
          <ul className="space-y-1" aria-label={CATEGORY_LIST_NAMES[category]}>
            {/* By slug: a re-analysis recreates the rows with new ids. */}
            {group.map((skill) => (
              <SkillBar key={skill.skill.slug} skill={skill} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
