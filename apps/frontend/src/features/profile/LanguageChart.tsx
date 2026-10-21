import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { ProfileLanguage } from '@/api/types'

import { languageRows, percent } from './languages'

export function LanguageChart({ languages }: { languages: readonly ProfileLanguage[] }) {
  const rows = languageRows(languages)
  if (rows.length === 0) {
    return <p className="text-muted-foreground text-sm">No languages detected yet.</p>
  }
  return (
    <div className="space-y-3">
      <div className="h-56 w-full" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }}>
            <XAxis type="number" domain={[0, 1]} tickFormatter={percent} hide />
            <YAxis type="category" dataKey="name" width={110} tickLine={false} axisLine={false} />
            <Tooltip formatter={(value) => percent(Number(value))} cursor={false} />
            <Bar dataKey="share" fill="var(--color-primary)" radius={4} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {/* The chart's accessible equivalent. */}
      <ul
        className="text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 text-sm"
        aria-label="Languages"
      >
        {rows.map((row) => (
          <li key={row.name}>
            <span className="text-foreground">{row.name}</span> {percent(row.share)}
          </li>
        ))}
      </ul>
    </div>
  )
}
