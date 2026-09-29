import { ChevronDown, ChevronRight } from 'lucide-react'
import { useId, useState } from 'react'

import type { DeveloperSkill } from '@/api/types'

import { CATEGORY_LABELS, SOURCE_LABELS, evidenceLabel, groupByCategory } from './evidence'

const date = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })

function SkillEvidenceList({ skill, id }: { skill: DeveloperSkill; id: string }) {
  return (
    <ul
      id={id}
      className="mt-2 space-y-1 pl-6 text-sm"
      aria-label={`Evidence for ${skill.skill.name}`}
    >
      {skill.evidence.map((item, index) => (
        <li key={index} className="text-muted-foreground">
          <span className="text-foreground">{SOURCE_LABELS[item.source]}</span>
          {item.repository && (
            <>
              {' · '}
              <a
                href={item.repository.html_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
              >
                {item.repository.full_name}
              </a>
            </>
          )}
          {item.detail && ` · ${item.detail}`}
          {item.observed_at && ` · ${date.format(new Date(item.observed_at))}`}
        </li>
      ))}
    </ul>
  )
}

function SkillBar({ skill }: { skill: DeveloperSkill }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const label = evidenceLabel(skill.evidence_summary)
  // Bar length reflects the strength of evidence; no number is shown (SRS-2 §15).
  const width = `${Math.max(Math.round(skill.confidence * 100), 4)}%`
  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((value) => !value)}
        className="hover:bg-secondary/60 grid w-full grid-cols-[1rem_8rem_1fr] items-center gap-3 rounded px-1 py-1 text-left"
      >
        {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        <span className="truncate text-sm font-medium">{skill.skill.name}</span>
        <span className="space-y-1">
          <span className="bg-secondary block h-2 overflow-hidden rounded-full" aria-hidden>
            <span className="bg-primary block h-full rounded-full" style={{ width }} />
          </span>
          <span className="text-muted-foreground block text-xs">{label}</span>
        </span>
      </button>
      {open && <SkillEvidenceList skill={skill} id={id} />}
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
          <ul className="space-y-1" aria-label={CATEGORY_LABELS[category]}>
            {group.map((skill) => (
              <SkillBar key={skill.id} skill={skill} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
