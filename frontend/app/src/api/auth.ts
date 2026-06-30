import { ApiError, apiClient } from './client'
import type { components } from './schema'

export type AuthMe = components['schemas']['AuthMeResponse']

export async function getCurrentUser(): Promise<AuthMe> {
  const { data } = await apiClient.GET('/auth/me')
  if (!data) throw new ApiError('Authentication response was empty')
  return data
}
