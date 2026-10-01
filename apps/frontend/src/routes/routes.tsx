import type { RouteObject } from 'react-router'

import { RequireAuth } from '@/features/auth/RequireAuth'
import { SavedPage } from '@/features/feedback/SavedPage'
import { RecommendationDetailPage } from '@/features/recommendations/RecommendationDetailPage'

import { AppShell } from './AppShell'
import { LandingPage } from './LandingPage'
import { OnboardingPage } from './OnboardingPage'
import { PrivacyPage } from './PrivacyPage'
import { SignedInLayout } from './SignedInLayout'

export const routes: RouteObject[] = [
  { path: '/', element: <LandingPage /> },
  { path: '/privacy', element: <PrivacyPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <SignedInLayout />,
        children: [
          { path: '/app', element: <AppShell /> },
          { path: '/app/recommendations/:id', element: <RecommendationDetailPage /> },
          { path: '/app/saved', element: <SavedPage /> },
          { path: '/onboarding', element: <OnboardingPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <LandingPage /> },
]
