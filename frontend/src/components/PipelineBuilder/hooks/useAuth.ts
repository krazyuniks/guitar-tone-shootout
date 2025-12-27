/**
 * Hook for checking authentication status.
 */
import { useQuery } from '@tanstack/react-query';
import { api, type AuthStatus } from '@/lib/api';

/**
 * Check if the current user is authenticated.
 */
export function useAuth() {
  return useQuery({
    queryKey: ['auth', 'status'],
    queryFn: () => api.get<AuthStatus>('/auth/me'),
    retry: false,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}
