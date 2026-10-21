import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'

import './index.css'
import { createQueryClient } from './app/queryClient'
import { routes } from './routes/routes'

const router = createBrowserRouter(routes)
const queryClient = createQueryClient({
  navigate: (path) => router.navigate(path, { replace: true }),
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
