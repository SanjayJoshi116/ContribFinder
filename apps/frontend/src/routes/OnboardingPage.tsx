import { useEffect } from 'react'
import { Navigate, useNavigate } from 'react-router'

import { Button } from '@/components/ui/button'
import { GITHUB_SIGN_IN_URL } from '@/features/auth/api'
import { isActive, isStalled } from '@/app/jobTransitions'
import { useStartSync, useSyncStatus } from '@/features/sync/api'
import { STALLED_NOTICE, failureMessage } from '@/features/sync/messages'
import { SyncSteps } from '@/features/sync/SyncSteps'

export function OnboardingPage() {
  const status = useSyncStatus()
  const start = useStartSync()
  const navigate = useNavigate()
  const job = status.data?.job ?? null

  useEffect(() => {
    if (job?.status === 'COMPLETED') navigate('/app', { replace: true })
  }, [job?.status, navigate])

  if (status.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (status.isError) {
    return <p role="alert">Could not load sync status. Please refresh the page.</p>
  }
  // Already synced and nothing running: nothing to onboard.
  if (status.data.last_synced_at && !isActive(job)) return <Navigate to="/app" replace />

  const failed = job && (job.status === 'FAILED' || job.status === 'CANCELLED')
  const failure = failed ? failureMessage(job) : null
  const stalled = isStalled(job)

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Analyzing your GitHub profile…</h1>
        <p className="text-muted-foreground">
          We&apos;re reading your public profile, profile README and repositories. This runs in the
          background — you can leave this page and come back.
        </p>
      </div>

      {job ? (
        <div className="rounded-lg border p-4">
          <SyncSteps job={job} />
          {stalled && (
            <p role="status" className="text-muted-foreground mt-4 text-sm">
              {STALLED_NOTICE}, or try again.
            </p>
          )}
          {job.status === 'RETRYING' && (
            <p className="text-muted-foreground mt-4 text-sm">
              GitHub asked us to slow down or didn&apos;t respond. Retrying automatically…
            </p>
          )}
        </div>
      ) : (
        <p className="text-muted-foreground">No sync has started yet.</p>
      )}

      {failure && (
        <p role="alert" className="border-destructive/40 text-destructive rounded-md border p-3">
          {failure.text}
        </p>
      )}

      {failure?.needsSignIn ? (
        <Button asChild>
          <a href={GITHUB_SIGN_IN_URL}>Sign in with GitHub again</a>
        </Button>
      ) : (
        (!job || failed || stalled) && (
          <Button disabled={start.isPending} onClick={() => start.mutate()}>
            {job ? 'Try again' : 'Start sync'}
          </Button>
        )
      )}
      {start.isError && (
        <p role="alert" className="text-destructive text-sm">
          {start.error.message}
        </p>
      )}
    </section>
  )
}
