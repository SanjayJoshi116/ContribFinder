import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

import { preloadLazyComponents } from '@/app/lazyLoaders'
import { forgetScrolledEntries } from '@/lib/useScrollToHash'

// Test files run in parallel workers; under load (Windows, CI) a first render with mocked
// fetches can take longer than Testing Library's 1 s default for findBy*/waitFor.
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
  forgetScrolledEntries()
})

// Lazy components load on first render. Recharts (LanguageChart) evaluates for about a second
// on first import and would land inside whichever test is running when it resolves (P-3), so
// every test file pays for all of them here. A component made lazy through `lazyLoaders` is
// preloaded automatically; never call `lazy()` with a loader outside the registry.
await preloadLazyComponents()
