import type { components } from './schema'

type Schemas = components['schemas']

export type Me = Schemas['Me']
export type DisconnectResult = Schemas['DisconnectResult']
export type ApiErrorBody = Schemas['Error']
export type SyncJob = Schemas['SyncJob']
export type SyncStatus = Schemas['SyncStatus']
export type SyncStepState = SyncJob['steps'][string]
export type GitHubProfile = Schemas['GitHubProfile']
export type Repository = Schemas['Repository']
export type RepositoryPage = Schemas['PaginatedRepositoryList']
