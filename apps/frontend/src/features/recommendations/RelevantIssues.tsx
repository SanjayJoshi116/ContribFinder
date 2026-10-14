import { Link } from 'react-router'

import type { RelevantIssue } from '@/api/types'

import { CONTRIBUTION_TYPE_TEXT, difficultyText } from './messages'

/** Issues picked for the developer: part of ContribFinder's analysis, best first. */
export function RelevantIssues({ issues }: { issues: RelevantIssue[] }) {
  return (
    <div className="space-y-2">
      <h3 id="relevant-issues" className="text-sm font-medium">
        Relevant issues
      </h3>
      {issues.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No open issues matching your profile were found in this project.
        </p>
      ) : (
        <ul className="space-y-2" aria-labelledby="relevant-issues">
          {issues.map((issue) => (
            <li key={issue.id} className="space-y-0.5 rounded border p-2 text-sm">
              <Link
                to={`/app/issues/${issue.id}`}
                className="font-medium break-words hover:underline"
              >
                #{issue.number} {issue.title}
              </Link>
              <p className="text-muted-foreground text-xs">
                Type: {CONTRIBUTION_TYPE_TEXT[issue.contribution_type]} · Difficulty:{' '}
                {difficultyText(issue.difficulty)}
              </p>
              {issue.reasons[0] && <p className="text-xs">{issue.reasons[0].text}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
