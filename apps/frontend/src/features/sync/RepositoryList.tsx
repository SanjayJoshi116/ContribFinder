import type { Repository } from '@/api/types'
import { ExternalLink } from '@/components/ExternalLink'

export function RepositoryList({ repositories }: { repositories: readonly Repository[] }) {
  if (repositories.length === 0) {
    return <p className="text-muted-foreground text-sm">No public repositories found.</p>
  }
  return (
    <ul className="divide-y rounded-lg border" aria-label="Repositories">
      {repositories.map((repo) => (
        <li key={repo.id} className="space-y-1 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <ExternalLink href={repo.html_url} className="font-medium hover:underline">
              {repo.full_name}
            </ExternalLink>
            {repo.is_fork && <Badge>fork</Badge>}
            {repo.is_archived && <Badge>archived</Badge>}
          </div>
          {repo.description && <p className="text-muted-foreground text-sm">{repo.description}</p>}
          <div className="text-muted-foreground flex flex-wrap gap-x-3 gap-y-1 text-xs">
            {repo.primary_language && <span>{repo.primary_language}</span>}
            <span>★ {repo.stars}</span>
            {repo.topics.map((topic) => (
              <span key={topic} className="bg-secondary rounded px-1.5 py-0.5">
                {topic}
              </span>
            ))}
          </div>
        </li>
      ))}
    </ul>
  )
}

function Badge({ children }: { children: string }) {
  return (
    <span className="text-muted-foreground rounded border px-1.5 py-0.5 text-xs">{children}</span>
  )
}
