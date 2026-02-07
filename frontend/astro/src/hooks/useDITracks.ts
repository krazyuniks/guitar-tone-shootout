/**
 * TanStack Query hooks for DI tracks.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  diTrackApi,
  type DITrackListParams,
  type DITrackUploadParams,
} from '@/lib/api';

/**
 * Query key factory for DI tracks.
 */
export const diTrackKeys = {
  all: ['di-tracks'] as const,
  lists: () => [...diTrackKeys.all, 'list'] as const,
  list: (params: DITrackListParams) =>
    [...diTrackKeys.lists(), params] as const,
  details: () => [...diTrackKeys.all, 'detail'] as const,
  detail: (id: string) => [...diTrackKeys.details(), id] as const,
};

/**
 * Fetch paginated list of DI tracks with optional filters.
 */
export function useDITracks(params: DITrackListParams = {}) {
  return useQuery({
    queryKey: diTrackKeys.list(params),
    queryFn: () => diTrackApi.list(params),
  });
}

/**
 * Fetch a single DI track by ID.
 */
export function useDITrack(id: string) {
  return useQuery({
    queryKey: diTrackKeys.detail(id),
    queryFn: () => diTrackApi.get(id),
    enabled: !!id,
  });
}

/**
 * Upload a new DI track with metadata.
 * Invalidates the list query on success.
 */
export function useUploadDITrack() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, params }: { file: File; params: DITrackUploadParams }) =>
      diTrackApi.upload(file, params),
    onSuccess: (newTrack) => {
      // Invalidate all list queries
      queryClient.invalidateQueries({ queryKey: diTrackKeys.lists() });
      // Optionally set the new track in cache
      queryClient.setQueryData(diTrackKeys.detail(newTrack.id), newTrack);
    },
  });
}

/**
 * Delete a DI track.
 * Invalidates the list query and removes the detail from cache on success.
 */
export function useDeleteDITrack() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => diTrackApi.delete(id),
    onSuccess: (_, deletedId) => {
      // Invalidate all list queries
      queryClient.invalidateQueries({ queryKey: diTrackKeys.lists() });
      // Remove the deleted track from cache
      queryClient.removeQueries({ queryKey: diTrackKeys.detail(deletedId) });
    },
  });
}
