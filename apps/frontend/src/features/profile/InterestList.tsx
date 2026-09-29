import type { DeveloperInterest } from '@/api/types'

const SOURCE_LABELS: Record<DeveloperInterest['evidence'][number]['source'], string> = {
  readme: 'Profile README',
  repo_description: 'Repository description',
  topic: 'Repository topic',
  contribution: 'Contribution',
}

export function InterestList({ interests }: { interests: readonly DeveloperInterest[] }) {
  if (interests.length === 0) {
    return <p className="text-muted-foreground text-sm">No interests detected yet.</p>
  }
  return (
    <ul className="space-y-2" aria-label="Interests">
      {interests.map(({ id, interest, evidence }) => (
        <li key={id}>
          <details className="rounded-lg border px-3 py-2">
            <summary className="cursor-pointer text-sm">
              <span className="font-medium">{interest.name}</span>
              <span className="text-muted-foreground">
                {' '}
                · {evidence.length} {evidence.length === 1 ? 'signal' : 'signals'}
              </span>
            </summary>
            <ul className="text-muted-foreground mt-2 space-y-1 text-sm">
              {evidence.map((item, index) => (
                <li key={index}>
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
                </li>
              ))}
            </ul>
          </details>
        </li>
      ))}
    </ul>
  )
}
