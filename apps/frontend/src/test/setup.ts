import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// Test files run in parallel workers; under load (Windows, CI) a first render with mocked
// fetches can take longer than Testing Library's 1 s default for findBy*/waitFor.
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
})

// AppShell loads LanguageChart (Recharts) lazily. Its first import evaluates for about a second
// and would land inside whichever test is running when it resolves (P-3), so every test file
// pays it here instead. Preload any other lazy component the same way.
await import('@/features/profile/LanguageChart')
