import { Suspense, lazy } from 'react'
import { Navigate } from 'react-router'

import { isActive, isStalled } from '@/app/jobTransitions'
import { lazyLoaders } from '@/app/lazyLoaders'
import { formatDateTime } from '@/lib/format'
import { Loaded } from '@/components/Loaded'
import { Button } from '@/components/ui/button'
import { useSignedInUser } from '@/features/auth/api'
import { DataSection } from '@/features/auth/DataSection'
import { DisconnectSection } from '@/features/auth/DisconnectSection'
import { DiscoveryCard } from '@/features/discovery/DiscoveryCard'
import { useDeveloperProfile, useInterests, useSkills } from '@/features/profile/api'
import { InterestList } from '@/features/profile/InterestList'
import { SkillGroups } from '@/features/profile/SkillGroups'
import { RecommendationList } from '@/features/recommendations/RecommendationList'
import { useGitHubProfile, useRepositories, useStartSync, useSyncStatus } from '@/features/sync/api'
import { failureMessage, startErrorText } from '@/features/sync/messages'
import { STAGE_TEXT, usePipelineStage } from '@/features/sync/pipeline'
import { RepositoryList } from '@/features/sync/RepositoryList'

const LanguageChart = lazy(lazyLoaders.LanguageChart)

/** A first load that failed: never shown as an empty list (ROUTE-4). */
function LoadFailed({ what }: { what: string }) {
  return (
    <p role="alert" className="text-destructive text-sm">
      Could not load your {what}. Please refresh the page.
    </p>
  )
}

export function AppShell() {
  const me = useSignedInUser()
  const status = useSyncStatus()
  const synced = !!status.data?.last_synced_at
  const profile = useGitHubProfile(synced)
  const repositories = useRepositories(synced)
  const developer = useDeveloperProfile(synced)
  // From the data, not the last fetch: a failed refetch keeps the shown profile (ROUTE-3).
  const skills = useSkills(!!developer.data)
  const interests = useInterests(!!developer.data)
  const start = useStartSync()
  const stage = usePipelineStage()

  if (status.isPending) return <p className="text-muted-foreground">Loading…</p>
  // Only without data: a failed poll keeps the page (ROUTE-2).
  if (!status.data) {
    return <p role="alert">Could not load your profile. Please refresh the page.</p>
  }
  if (!synced) return <Navigate to="/onboarding" replace />

  const job = status.data.job
  // A stalled sync does not block a new one: starting replaces it (worker_lost).
  const syncing = isActive(job) && !isStalled(job)
  const lastFailure = job && job.status === 'FAILED' ? failureMessage(job) : null
  const name = profile.data?.name || me.display_name || me.github_username || 'there'

  return (
    <>
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold">Welcome, {name}</h1>
        {profile.data?.bio && <p className="text-muted-foreground">{profile.data.bio}</p>}
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-muted-foreground">
            Last synced {formatDateTime(status.data.last_synced_at!)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={syncing || start.isPending}
            onClick={() => start.mutate()}
          >
            Refresh
          </Button>
          {stage && (
            <span role="status" className="text-muted-foreground">
              {STAGE_TEXT[stage]}
            </span>
          )}
        </div>
        {start.isError && (
          <p role="status" className="text-muted-foreground text-sm">
            {startErrorText(start.error, start.submittedAt)}
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
      ) : !developer.data ? (
        <p role="status" className="text-muted-foreground text-sm">
          {developer.error?.code === 'not_analyzed'
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

          <RecommendationList />

          <section className="space-y-3" aria-labelledby="skills-heading">
            <h2 id="skills-heading" className="font-medium">
              Skills
            </h2>
            <Loaded query={skills} failed={<LoadFailed what="skills" />}>
              {(data) => <SkillGroups skills={data.results} />}
            </Loaded>
          </section>

          <section className="space-y-3" aria-labelledby="interests-heading">
            <h2 id="interests-heading" className="font-medium">
              Interests
            </h2>
            <Loaded query={interests} failed={<LoadFailed what="interests" />}>
              {(data) => <InterestList interests={data.results} />}
            </Loaded>
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
        <Loaded query={repositories} failed={<LoadFailed what="repositories" />}>
          {(data) => <RepositoryList repositories={data.results} />}
        </Loaded>
      </section>

      <DataSection />

      <DisconnectSection />
    </>
  )
}
