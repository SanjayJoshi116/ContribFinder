import type { RouteObject } from 'react-router'

import { RouteError } from '@/components/RouteError'
import { RequireAuth } from '@/features/auth/RequireAuth'
import { SavedPage } from '@/features/feedback/SavedPage'
import { IssueDetailPage } from '@/features/issues/IssueDetailPage'
import { RecommendationDetailPage } from '@/features/recommendations/RecommendationDetailPage'

import { AppShell } from './AppShell'
import { LandingPage } from './LandingPage'
import { OnboardingPage } from './OnboardingPage'
import { PrivacyPage } from './PrivacyPage'
import { RouteId } from './RouteId'
import { SignedInLayout } from './SignedInLayout'

// The root route's error screen covers every page, signed in or not (CMP-1).
export const routes: RouteObject[] = [
  {
    errorElement: <RouteError />,
    children: [
      { path: '/', element: <LandingPage /> },
      { path: '/privacy', element: <PrivacyPage /> },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <SignedInLayout />,
            children: [
              { path: '/app', element: <AppShell /> },
              {
                path: '/app/recommendations/:id',
                element: (
                  <RouteId invalid="This link doesn't point to a recommendation.">
                    {(id) => <RecommendationDetailPage id={id} />}
                  </RouteId>
                ),
              },
              {
                path: '/app/issues/:id',
                element: (
                  <RouteId invalid="This link doesn't point to an issue.">
                    {(id) => <IssueDetailPage id={id} />}
                  </RouteId>
                ),
              },
              { path: '/app/saved', element: <SavedPage /> },
              { path: '/onboarding', element: <OnboardingPage /> },
            ],
          },
        ],
      },
      { path: '*', element: <LandingPage /> },
    ],
  },
]
