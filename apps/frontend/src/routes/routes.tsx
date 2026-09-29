import type { RouteObject } from 'react-router'

import { RequireAuth } from '@/features/auth/RequireAuth'

import { AppShell } from './AppShell'
import { LandingPage } from './LandingPage'
import { OnboardingPage } from './OnboardingPage'
import { SignedInLayout } from './SignedInLayout'

export const routes: RouteObject[] = [
  { path: '/', element: <LandingPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <SignedInLayout />,
        children: [
          { path: '/app', element: <AppShell /> },
          { path: '/onboarding', element: <OnboardingPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <LandingPage /> },
]
