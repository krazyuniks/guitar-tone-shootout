/**
 * Hook for submitting jobs to the pipeline.
 */
import { useMutation } from '@tanstack/react-query';
import { api, type JobCreate, type JobResponse } from '@/lib/api';

interface SubmitJobParams {
  toneIds: number[];
  diTrackPath?: string;
  title?: string;
  description?: string;
}

/**
 * Submit a new job for processing.
 */
export function useJobSubmit() {
  return useMutation({
    mutationFn: async (params: SubmitJobParams): Promise<JobResponse> => {
      const payload: JobCreate = {
        config: {
          tones: params.toneIds,
          di_track_path: params.diTrackPath,
          title: params.title,
          description: params.description,
        },
      };
      return api.post<JobResponse>('/jobs', payload);
    },
  });
}

/**
 * Upload a DI track file and return its path.
 */
export function useFileUpload() {
  return useMutation({
    mutationFn: async (file: File): Promise<{ path: string }> => {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/v1/files/upload', {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({
          detail: `Upload failed: ${response.statusText}`,
        }));
        throw new Error(error.detail);
      }

      return response.json();
    },
  });
}
