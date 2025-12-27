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
