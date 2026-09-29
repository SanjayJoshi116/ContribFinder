import { useQuery } from '@tanstack/react-query'

import { ApiError, apiFetch } from '@/api/client'
import type { DeveloperProfile, InterestPage, SkillPage } from '@/api/types'

// Under ['profile'], so a completed sync (useSyncStatus) invalidates these too.
export const developerProfileKey = ['profile', 'developer'] as const
export const skillsKey = ['profile', 'skills'] as const
export const interestsKey = ['profile', 'interests'] as const

/** The analyzed profile. A 404 `not_analyzed` means it is still being prepared. */
export function useDeveloperProfile(enabled = true) {
  return useQuery<DeveloperProfile, ApiError>({
    queryKey: developerProfileKey,
    queryFn: () => apiFetch<DeveloperProfile>('/profile'),
    enabled,
  })
}

/** All detected skills with evidence (a profile has far fewer than one page of 200). */
export function useSkills(enabled = true) {
  return useQuery<SkillPage, ApiError>({
    queryKey: skillsKey,
    queryFn: () => apiFetch<SkillPage>('/profile/skills?page_size=200'),
    enabled,
  })
}

export function useInterests(enabled = true) {
  return useQuery<InterestPage, ApiError>({
    queryKey: interestsKey,
    queryFn: () => apiFetch<InterestPage>('/profile/interests?page_size=200'),
    enabled,
  })
}
