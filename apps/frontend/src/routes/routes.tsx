import type { RouteObject } from 'react-router'

import { RequireAuth } from '@/features/auth/RequireAuth'

import { AppShell } from './AppShell'
import { LandingPage } from './LandingPage'

export const routes: RouteObject[] = [
  { path: '/', element: <LandingPage /> },
  {
    element: <RequireAuth />,
    children: [{ path: '/app', element: <AppShell /> }],
  },
  { path: '*', element: <LandingPage /> },
]
