import { useQuery } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type { IssueDetail } from '@/api/types'

// Under ['profile'], so a completed sync refreshes it with everything else.
export const issueKey = (id: number) => ['profile', 'issues', id] as const

export function useIssue(id: number) {
  return useQuery<IssueDetail, ApiError>({
    queryKey: issueKey(id),
    queryFn: () => apiFetch<IssueDetail>(`/issues/${id}`),
    enabled: Number.isInteger(id) && id > 0,
  })
}
