/**
 * Hook for fetching tones from Tone 3000 API.
 */
import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { api, type PaginatedTones, type Gear, type Platform } from '@/lib/api';

export interface ToneSearchParams {
  query?: string;
  gear?: Gear;
  platform?: Platform;
  page?: number;
  per_page?: number;
}

/**
 * Fetch user's created tones.
 */
export function useMyTones(page = 1, perPage = 20) {
  return useQuery({
    queryKey: ['tones', 'mine', page, perPage],
    queryFn: () =>
      api.get<PaginatedTones>(`/tones/mine?page=${page}&per_page=${perPage}`),
  });
}

/**
 * Fetch user's favorited tones.
 */
export function useFavoriteTones(page = 1, perPage = 20) {
  return useQuery({
    queryKey: ['tones', 'favorites', page, perPage],
    queryFn: () =>
      api.get<PaginatedTones>(`/tones/favorites?page=${page}&per_page=${perPage}`),
  });
}

/**
 * Search tones with filters.
 */
export function useSearchTones(params: ToneSearchParams) {
  const searchParams = new URLSearchParams();
  if (params.query) searchParams.set('query', params.query);
  if (params.gear) searchParams.set('gear', params.gear);
  if (params.platform) searchParams.set('platform', params.platform);
  searchParams.set('page', String(params.page ?? 1));
  searchParams.set('per_page', String(params.per_page ?? 20));

  return useQuery({
    queryKey: ['tones', 'search', params],
    queryFn: () =>
      api.get<PaginatedTones>(`/tones/search?${searchParams.toString()}`),
  });
}

/**
 * Infinite scroll search for tones.
 */
export function useInfiniteSearchTones(params: Omit<ToneSearchParams, 'page'>) {
  return useInfiniteQuery({
    queryKey: ['tones', 'search', 'infinite', params],
    queryFn: async ({ pageParam = 1 }) => {
      const searchParams = new URLSearchParams();
      if (params.query) searchParams.set('query', params.query);
      if (params.gear) searchParams.set('gear', params.gear);
      if (params.platform) searchParams.set('platform', params.platform);
      searchParams.set('page', String(pageParam));
      searchParams.set('per_page', String(params.per_page ?? 20));

      return api.get<PaginatedTones>(`/tones/search?${searchParams.toString()}`);
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.has_next ? lastPage.page + 1 : undefined,
  });
}
