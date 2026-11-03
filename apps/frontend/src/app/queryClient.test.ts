import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'

import { createQueryClient } from './queryClient'
import { meQueryKey } from './session'

const fail401 = (queryClient: ReturnType<typeof createQueryClient>, name: string) =>
  queryClient
    .fetchQuery({
      queryKey: ['profile', name],
      queryFn: () => Promise.reject(new ApiError(401, 'not_authenticated', 'Signed out.')),
    })
    .catch(() => undefined)

describe('createQueryClient', () => {
  it('reports a later 401 again when leaving for the sign-in page failed', async () => {
    const navigate = vi
      .fn<(path: string) => Promise<void>>()
      .mockRejectedValueOnce(new Error('navigation refused'))
      .mockResolvedValue(undefined)
    const queryClient = createQueryClient({ navigate, retryDelay: 0 })

    await fail401(queryClient, 'first')
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledTimes(1))
    await new Promise((resolve) => setTimeout(resolve, 0))
    await fail401(queryClient, 'second')

    await vi.waitFor(() => expect(navigate).toHaveBeenCalledTimes(2))
  })

  it('keeps the identity when leaving for the sign-in page failed', async () => {
    const navigate = vi
      .fn<(path: string) => Promise<void>>()
      .mockRejectedValueOnce(new Error('navigation refused'))
    const queryClient = createQueryClient({ navigate, retryDelay: 0 })
    const me = { id: 1, github_username: 'dev' }
    queryClient.setQueryData(meQueryKey, me)

    await fail401(queryClient, 'first')
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledTimes(1))
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(queryClient.getQueryData(meQueryKey)).toEqual(me)
  })

  it('reports a 401 once while leaving succeeds', async () => {
    const navigate = vi.fn<(path: string) => Promise<void>>().mockResolvedValue(undefined)
    const queryClient = createQueryClient({ navigate, retryDelay: 0 })

    await fail401(queryClient, 'first')
    await fail401(queryClient, 'second')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(navigate).toHaveBeenCalledTimes(1)
  })
})
