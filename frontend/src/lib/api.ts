/**
 * API client for Guitar Tone Shootout backend.
 * Uses the Vite proxy configuration to forward /api requests to the backend.
 */

const API_BASE = '/api/v1';

interface ApiError {
  detail: string;
}

class ApiClient {
  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE}${path}`;
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include', // Include cookies for session auth
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`,
      }));
      throw new Error(error.detail);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'GET' });
  }

  post<T>(path: string, data?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  put<T>(path: string, data: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  patch<T>(path: string, data: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' });
  }
}

export const api = new ApiClient();

// Type definitions for API responses
export interface User {
  id: number;
  tone3000_id: number;
  username: string;
  avatar_url: string | null;
}

export interface Job {
  id: string;
  user_id: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  job_type: string;
  created_at: string;
  updated_at: string;
  result: unknown;
  error: string | null;
}

export interface AuthStatus {
  authenticated: boolean;
  user: User | null;
}

// Tone 3000 types
export type Gear = 'amp' | 'full-rig' | 'pedal' | 'outboard' | 'ir';
export type Platform = 'nam' | 'ir' | 'aida-x';

export interface Tag {
  id: number;
  name: string;
}

export interface Make {
  id: number;
  name: string;
}

export interface Tone {
  id: number;
  title: string;
  description: string | null;
  gear: Gear;
  platform: Platform;
  tags: Tag[];
  makes: Make[];
  models_count: number;
  downloads_count: number;
}

export interface PaginatedTones {
  data: Tone[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
}

// Job types
export interface JobCreate {
  config: {
    tones: number[];
    di_track_path?: string;
    title?: string;
    description?: string;
  };
}

export interface JobResponse {
  id: string;
  user_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  message: string | null;
  config: string | null;
  started_at: string | null;
  completed_at: string | null;
  result_path: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

// Shootout types
export interface ShootoutListItem {
  id: string;
  name: string;
  description: string | null;
  is_processed: boolean;
  output_path: string | null;
  tone_count: number;
  created_at: string;
  updated_at: string;
}

export interface ShootoutListResponse {
  shootouts: ShootoutListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AudioMetrics {
  duration_seconds: number;
  sample_rate: number;
  core: {
    rms_dbfs: number;
    peak_dbfs: number;
    crest_factor_db: number;
    dynamic_range_db: number;
  };
  spectral: {
    spectral_centroid_hz: number;
    bass_energy_ratio: number;
    mid_energy_ratio: number;
    treble_energy_ratio: number;
  };
  advanced: {
    lufs_integrated: number;
    transient_density: number;
    attack_time_ms: number;
    sustain_decay_rate_db_s: number;
  };
}

export interface AIEvaluation {
  model_name: string;
  model_version: string | null;
  tone_description: string;
  strengths: string[];
  weaknesses: string[];
  recommended_genres: string[];
  comparison_notes: string | null;
  overall_rating: number | null;
}

export interface ToneSelection {
  id: string;
  tone3000_tone_id: number;
  tone3000_model_id: number;
  tone_title: string;
  model_name: string;
  model_size: string;
  gear_type: string;
  display_name: string | null;
  description: string | null;
  ir_path: string | null;
  highpass: boolean;
  effects_json: string | null;
  position: number;
  start_ms: number | null;
  end_ms: number | null;
  audio_metrics: AudioMetrics | null;
  ai_evaluation: AIEvaluation | null;
  created_at: string;
}

export interface ProcessingMetadata {
  pipeline_version: string;
  nam_version: string | null;
  ffmpeg_version: string | null;
  python_version: string | null;
  processed_at: string;
  processing_duration_seconds: number | null;
  worker_id: string | null;
  config_hash: string | null;
  audio_settings: Record<string, unknown>;
  video_settings: Record<string, unknown>;
}

export interface ShootoutDetail {
  id: string;
  name: string;
  description: string | null;
  di_track_path: string;
  di_track_original_name: string;
  output_format: string;
  sample_rate: number;
  guitar: string | null;
  pickup: string | null;
  di_track_description: string | null;
  is_processed: boolean;
  output_path: string | null;
  processing_metadata: ProcessingMetadata | null;
  tone_selections: ToneSelection[];
  created_at: string;
  updated_at: string;
}
