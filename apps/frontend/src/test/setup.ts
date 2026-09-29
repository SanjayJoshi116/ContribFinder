import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// Test files run in parallel workers; under load (Windows, CI) a first render with mocked
// fetches can take longer than Testing Library's 1 s default for findBy*/waitFor.
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
})
