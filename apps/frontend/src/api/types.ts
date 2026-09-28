import type { components } from './schema'

type Schemas = components['schemas']

export type Me = Schemas['Me']
export type DisconnectResult = Schemas['DisconnectResult']
export type ApiErrorBody = Schemas['Error']
