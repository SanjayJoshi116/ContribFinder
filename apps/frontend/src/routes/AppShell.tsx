import { Suspense, lazy } from 'react'
import { Navigate } from 'react-router'

import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/api'
import { DisconnectSection } from '@/features/auth/DisconnectSection'
import { DiscoveryCard } from '@/features/discovery/DiscoveryCard'
import { useDeveloperProfile, useInterests, useSkills } from '@/features/profile/api'
import { InterestList } from '@/features/profile/InterestList'
import { SkillGroups } from '@/features/profile/SkillGroups'
import {
  isActive,
  useGitHubProfile,
  useRepositories,
  useStartSync,
  useSyncStatus,
} from '@/features/sync/api'
import { failureMessage, formatWait } from '@/features/sync/messages'
import { RepositoryList } from '@/features/sync/RepositoryList'

// Recharts is large; load it only with the profile page's chart.
const LanguageChart = lazy(() =>
  import('@/features/profile/LanguageChart').then((m) => ({ default: m.LanguageChart })),
)

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export function AppShell() {
  const { data: me } = useMe()
  const status = useSyncStatus()
  const synced = !!status.data?.last_synced_at
  const profile = useGitHubProfile(synced)
  const repositories = useRepositories(synced)
  const developer = useDeveloperProfile(synced)
  const analyzed = developer.isSuccess
  const skills = useSkills(analyzed)
  const interests = useInterests(analyzed)
  const start = useStartSync()

  if (status.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (status.isError) {
    return <p role="alert">Could not load your profile. Please refresh the page.</p>
  }
  if (!synced) return <Navigate to="/onboarding" replace />

  const job = status.data.job
  const syncing = isActive(job)
  const lastFailure = job && job.status === 'FAILED' ? failureMessage(job) : null
  const name = profile.data?.name || me?.display_name || me?.github_username || 'there'
  const repos = repositories.data?.results ?? []

  return (
    <>
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold">Welcome, {name}</h1>
        {profile.data?.bio && <p className="text-muted-foreground">{profile.data.bio}</p>}
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-muted-foreground">
            Last synced {dateTime.format(new Date(status.data.last_synced_at!))}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={syncing || start.isPending}
            onClick={() => start.mutate()}
          >
            {syncing ? 'Syncing…' : 'Refresh'}
          </Button>
        </div>
        {start.isError && (
          <p role="status" className="text-muted-foreground text-sm">
            {start.error.code === 'sync_cooldown' && start.error.retryAfter
              ? `Your data was synced recently. You can refresh again in ${formatWait(start.error.retryAfter)}.`
              : start.error.message}
          </p>
        )}
        {lastFailure && (
          <p role="alert" className="text-destructive text-sm">
            Last refresh failed: {lastFailure.text}
          </p>
        )}
      </section>

      {developer.isPending ? (
        <p className="text-muted-foreground text-sm">Loading your profile…</p>
      ) : !analyzed ? (
        <p role="status" className="text-muted-foreground text-sm">
          {developer.error.code === 'not_analyzed'
            ? 'Your developer profile is being prepared from your synced data. It will appear here once the next sync finishes.'
            : 'Could not load your developer profile. Please refresh the page.'}
        </p>
      ) : (
        <>
          <section className="space-y-2" aria-labelledby="summary-heading">
            <h2 id="summary-heading" className="font-medium">
              Summary
            </h2>
            <p>{developer.data.summary}</p>
            <p className="text-muted-foreground text-xs">
              Built from your public GitHub data. Skill bars show how much evidence we found, not
              how good you are.
            </p>
          </section>

          <DiscoveryCard />

          <section className="space-y-3" aria-labelledby="skills-heading">
            <h2 id="skills-heading" className="font-medium">
              Skills
            </h2>
            {skills.isPending ? (
              <p className="text-muted-foreground text-sm">Loading…</p>
            ) : (
              <SkillGroups skills={skills.data?.results ?? []} />
            )}
          </section>

          <section className="space-y-3" aria-labelledby="interests-heading">
            <h2 id="interests-heading" className="font-medium">
              Interests
            </h2>
            {interests.isPending ? (
              <p className="text-muted-foreground text-sm">Loading…</p>
            ) : (
              <InterestList interests={interests.data?.results ?? []} />
            )}
          </section>

          <section className="space-y-3" aria-labelledby="languages-heading">
            <h2 id="languages-heading" className="font-medium">
              Languages
            </h2>
            <Suspense fallback={<p className="text-muted-foreground text-sm">Loading…</p>}>
              <LanguageChart languages={developer.data.languages} />
            </Suspense>
          </section>
        </>
      )}

      <section className="space-y-3">
        <h2 className="font-medium">
          Repositories{' '}
          {repositories.data && (
            <span className="text-muted-foreground font-normal">({repositories.data.count})</span>
          )}
        </h2>
        {repositories.isPending ? (
          <p className="text-muted-foreground text-sm">Loading…</p>
        ) : (
          <RepositoryList repositories={repos} />
        )}
      </section>

      <DisconnectSection />
    </>
  )
}
