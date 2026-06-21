/**
 * API client for Guitar Tone Shootout backend.
 * Uses the Vite proxy configuration to forward /api requests to the backend.
 *
 * STORY-008: API client uses error handling utilities to normalize error responses.
 * - Throws ApiError class with code, message, requestId properties
 * - Sanitizes error messages before throwing
 * - Preserves original response for debugging
 */

import { getErrorMessage, extractErrorCode } from './error-handling';

const API_BASE = '/api';

/**
 * Shape of error responses from the API.
 * Handles multiple formats for backwards compatibility.
 */
interface ApiErrorResponse {
  detail?: string;
  message?: string;
  code?: string;
  request_id?: string;
  error?: {
    message?: string;
    code?: string;
  };
}

/**
 * Custom error class for API errors.
 * Carries error code, sanitized message, and request ID for support reference.
 *
 * @example
 * ```ts
 * try {
 *   await api.get('/protected-resource');
 * } catch (error) {
 *   if (error instanceof ApiError) {
 *     console.log(error.code);      // 'AUTH_001'
 *     console.log(error.message);   // 'Authentication required'
 *     console.log(error.requestId); // 'req-123-456'
 *   }
 * }
 * ```
 */
export class ApiError extends Error {
  /** Error code in CATEGORY_NNN format (e.g., AUTH_001, VAL_002) or null */
  public readonly code: string | null;

  /** Request ID for support reference and log correlation */
  public readonly requestId: string | null;

  /** Original error response from the API (for debugging in dev mode) */
  public readonly originalResponse: unknown;

  constructor(
    message: string,
    code: string | null = null,
    requestId: string | null = null,
    originalResponse: unknown = null
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.requestId = requestId;
    this.originalResponse = originalResponse;

    // Maintain proper stack trace in V8 environments
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ApiError);
    }
  }
}

/**
 * Extract request_id from error response.
 * Handles both flat and nested error shapes.
 */
function extractRequestId(errorData: ApiErrorResponse): string | null {
  // Direct request_id (flat format or alongside nested error)
  if (typeof errorData.request_id === 'string' && errorData.request_id.trim()) {
    return errorData.request_id;
  }
  return null;
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
      // Try to parse JSON error response, fallback to generic HTTP error
      const errorData: ApiErrorResponse = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`,
      }));

      // Extract and sanitize error message using error handling utilities
      const sanitizedMessage = getErrorMessage(errorData);

      // Extract error code (returns null if not present or invalid format)
      const errorCode = extractErrorCode(errorData);

      // Extract request_id for support reference
      const requestId = extractRequestId(errorData);

      // Throw ApiError with sanitized message, code, request_id, and original response
      throw new ApiError(sanitizedMessage, errorCode, requestId, errorData);
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

export type License = 'cc-by' | 'cc-by-sa' | 'cc-by-nc' | 'cc-by-nc-sa' | 'cc-by-nd' | 'cc-by-nc-nd' | 'cc0' | 'custom' | 't3k';
export type ModelSize = 'standard' | 'lite' | 'feather' | 'nano';

export interface Creator {
  id: string;
  username: string;
  avatar_url?: string | null;
  url?: string | null;  // Creator's profile URL on T3K
}

export interface Tone {
  id: string;
  title: string;
  description: string | null;
  gear: Gear;
  platform: Platform;
  tags: Tag[];
  makes: Make[];
  links: string[];  // External links (may include YouTube URLs)
  videos?: string[];  // YouTube video URLs from T3K
  images?: string[];  // Image URLs for the tone
  models_count: number;
  downloads_count: number;
  favorites_count: number;
  license: License | null;
  creator: Creator | null;
  created_at?: string | null;
  updated_at: string | null;
}

export interface ToneModel {
  id: number;
  name: string;
  size: ModelSize;
  model_url: string;
  tone_id: number;
  model_uuid?: string | null;
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

export type JobStatus = 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'dead_lettered';
export type JobType = 'shootout' | 'audio_segment' | 'video_composition' | 't3k_sync_full' | 't3k_sync_incremental';

export interface JobResponse {
  id: string;
  user_id: string;
  job_type: JobType;
  parent_job_id: string | null;
  depends_on: string[] | null;
  status: JobStatus;
  progress: number;
  message: string | null;
  config: string | null;
  started_at: string | null;
  completed_at: string | null;
  last_heartbeat: string | null;
  attempt: number;
  max_attempts: number;
  next_retry_at: string | null;
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

// Comparison types
export interface SegmentTimestamps {
  position: number;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  sample_rate: number;
}

export interface SegmentComparisonItem {
  segment_id: string;
  position: number;
  tone_title: string;
  timestamps: SegmentTimestamps | null;
  audio_metrics: AudioMetrics | null;
  ai_evaluation: AIEvaluation | null;
}

export interface MetricsAverages {
  rms_dbfs: number;
  peak_dbfs: number;
  spectral_centroid_hz: number;
  bass_energy_ratio: number;
  mid_energy_ratio: number;
  treble_energy_ratio: number;
  lufs_integrated: number;
}

export interface ShootoutComparisonResponse {
  shootout_id: string;
  shootout_name: string;
  segment_count: number;
  total_duration_ms: number;
  segments: SegmentComparisonItem[];
  averages: MetricsAverages | null;
}

// Full metadata types
export interface ProcessingVersions {
  pedalboard: string;
  nam_vst: string;
  ffmpeg: string;
  pipeline: string;
  python: string;
}

export interface AudioSettingsFull {
  sample_rate: number;
  bit_depth: number;
  channels: number;
  format: string;
}

export interface NormalizationSettings {
  input_target_rms_db: number;
  output_target_rms_db: number;
  method: string;
  headroom_db: number;
}

export interface FileHashes {
  di_track_sha256: string;
  nam_model_sha256: string | null;
  ir_sha256: string | null;
}

export interface ShootoutMetadataResponse {
  shootout_id: string;
  processing_versions: ProcessingVersions | null;
  normalization: NormalizationSettings | null;
  audio_settings: AudioSettingsFull | null;
  file_hashes: FileHashes | null;
  total_duration_ms: number;
  segment_count: number;
  processed_at: string | null;
  platform_info: string | null;
}

// DI Track types
export interface DITrackMetadata {
  guitar?: string;
  pickups?: string;
  tuning?: string;
  strings?: string;
  recording_interface?: string;
  notes?: string;
}

export interface DITrack {
  id: string;
  title: string;
  description?: string;
  file_path: string;
  file_size: number;
  checksum: string;
  sample_rate: number;
  duration_seconds: number;
  waveform_data?: string;  // base64
  is_system_track: boolean;
  source_url?: string;
  is_commercial: boolean;
  track_metadata?: DITrackMetadata;
  created_at: string;
  updated_at: string;
}

export interface DITrackListItem {
  id: string;
  user_id: string;
  title: string;
  description?: string;
  file_size: number;
  sample_rate: number;
  duration_seconds: number;
  is_system_track: boolean;
  is_commercial: boolean;
  guitar?: string;
  tuning?: string;
  pickups?: string;
  strings?: string;
  recording_interface?: string;
  created_at: string;
}

export interface DITrackUploadParams {
  title: string;
  description?: string;
  guitar?: string;
  pickups?: string;
  tuning?: string;
  strings?: string;
  recording_interface?: string;
}

export interface DITrackListParams {
  page?: number;
  pageSize?: number;
  guitar?: string;
  tuning?: string;
}

export interface DITrackListResponse {
  di_tracks: DITrackListItem[];
  total: number;
  page: number;
  page_size: number;
}

// DI Track API methods
export const diTrackApi = {
  /**
   * Upload a new DI track (multipart form).
   */
  async upload(file: File, params: DITrackUploadParams): Promise<DITrack> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', params.title);
    if (params.description) {
      formData.append('description', params.description);
    }
    if (params.guitar) {
      formData.append('guitar', params.guitar);
    }
    if (params.pickups) {
      formData.append('pickups', params.pickups);
    }
    if (params.tuning) {
      formData.append('tuning', params.tuning);
    }
    if (params.strings) {
      formData.append('strings', params.strings);
    }
    if (params.recording_interface) {
      formData.append('recording_interface', params.recording_interface);
    }

    const response = await fetch('/api/di-tracks/upload', {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });

    if (!response.ok) {
      // Try to parse JSON error response, fallback to generic HTTP error
      const errorData: ApiErrorResponse = await response.json().catch(() => ({
        detail: `Upload failed: ${response.statusText}`,
      }));

      // Extract and sanitize error message using error handling utilities
      const sanitizedMessage = getErrorMessage(errorData);

      // Extract error code (returns null if not present or invalid format)
      const errorCode = extractErrorCode(errorData);

      // Extract request_id for support reference
      const requestId = extractRequestId(errorData);

      // Throw ApiError with sanitized message, code, request_id, and original response
      throw new ApiError(sanitizedMessage, errorCode, requestId, errorData);
    }

    return response.json();
  },

  /**
   * List DI tracks with pagination and optional filtering.
   */
  list(params: DITrackListParams = {}): Promise<DITrackListResponse> {
    const { page = 1, pageSize = 20, guitar, tuning } = params;
    const queryParams = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (guitar) {
      queryParams.append('guitar', guitar);
    }
    if (tuning) {
      queryParams.append('tuning', tuning);
    }
    return api.get<DITrackListResponse>(`/di-tracks?${queryParams.toString()}`);
  },

  /**
   * Get a single DI track by ID.
   */
  get(id: string): Promise<DITrack> {
    return api.get<DITrack>(`/di-tracks/${id}`);
  },

  /**
   * Delete a DI track by ID.
   */
  delete(id: string): Promise<void> {
    return api.delete<void>(`/di-tracks/${id}`);
  },
};

// GearItem types
export type GearItemType = 'pedal' | 'amp' | 'ir' | 'full_rig' | 'post_effect';
// Note: ModelSize is already defined above in Tone 3000 types

export interface GearItemCreate {
  model_id: string;
  // gear_type is deprecated - derived from T3KModel's pack on the backend
  gear_type?: GearItemType;
  tone3000_model_id?: number;
  display_name?: string;
  is_favorite?: boolean;
  notes?: string;
  pack_title?: string;
}

export interface GearItem {
  id: string;
  user_id: string;
  gear_type: GearItemType;
  model_id: string;
  display_name: string | null;
  tone3000_tone_id: number | null;
  tone3000_model_id: number | null;
  pack_title: string | null;
  model_name: string | null;
  model_size: string | null;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

// GearItemListItem - used in list responses (includes tags)
export interface TagListItem {
  id: string;
  name: string;
  category: string | null;
}

export interface GearItemListItem {
  id: string;
  gear_type: GearItemType;
  model_id: string;
  display_name: string | null;
  is_favorite: boolean;
  tone3000_tone_id: number | null;
  tone3000_model_id: number | null;
  pack_title: string | null;
  model_name: string | null;
  model_size: string | null;
  pack_models_count: number | null;
  created_at: string;
  tags: TagListItem[];
}

export interface GearItemListResponse {
  gear_items: GearItemListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface GearItemListParams {
  search?: string;
  gear_type?: GearItemType;
  is_favorite?: boolean;
  model_size?: ModelSize;
  tag_ids?: string[];
  page?: number;
  page_size?: number;
  sort_by?: 'created_at' | 'display_name';
  sort_order?: 'asc' | 'desc';
}


// Signal Chain types
export type SignalChainPlatform = 'nam' | 'aida_x';
export type SignalChainGearType = 'pedal' | 'amp' | 'full_rig' | 'ir' | 'post_effect';

/**
 * V2 schema: Create signal chain block with reference to user's gear library.
 */
export interface SignalChainBlockCreate {
  /** Position in the chain (0-indexed) */
  position: number;
  /** Reference to UserGear item from user's library */
  user_gear_id: string;
}

/**
 * V2 schema: Signal chain block response.
 * Returns user_gear_id with gear_type cached for validation.
 */
export interface SignalChainBlock {
  id: string;
  signal_chain_id: string;
  position: number;
  /** Reference to UserGear item */
  user_gear_id: string;
  /** Cached gear type for validation */
  gear_type: SignalChainGearType;
  /** Optional: Display title (may be populated by backend) */
  title?: string;
  /** Optional: Display name (may be populated by backend) */
  name?: string;
}

export interface SignalChainCreate {
  name: string;
  platform?: SignalChainPlatform;
  blocks?: SignalChainBlockCreate[];
}

export interface SignalChainUpdate {
  name?: string;
  platform?: SignalChainPlatform;
  blocks?: SignalChainBlockCreate[];
}

export interface SignalChain {
  id: string;
  user_id: string;
  name: string;
  platform: SignalChainPlatform;
  created_at: string;
  updated_at: string;
  blocks: SignalChainBlock[];
}

export interface SignalChainListItem {
  id: string;
  name: string;
  platform: SignalChainPlatform;
  block_count: number;
  created_at: string;
  updated_at: string;
}

export interface SignalChainListResponse {
  signal_chains: SignalChainListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ValidationErrorDetail {
  code: string;
  message: string;
  position: number | null;
}

export interface SignalChainValidationResponse {
  is_valid: boolean;
  errors: ValidationErrorDetail[];
}

export interface SignalChainGuidanceBlock {
  gear_type: SignalChainGearType;
}

export interface SignalChainGuidanceRequest {
  blocks: SignalChainGuidanceBlock[];
}

export interface SignalChainGuidanceResponse {
  next_valid_gear_types: SignalChainGearType[];
  guidance_message: string;
  is_complete: boolean;
}

export interface SignalChainListParams {
  search?: string;
  platform?: SignalChainPlatform;
  page?: number;
  page_size?: number;
  sort_by?: 'created_at' | 'name' | 'updated_at';
  sort_order?: 'asc' | 'desc';
}

// Signal Chain API methods
export const signalChainApi = {
  /**
   * Create a new signal chain.
   */
  create(data: SignalChainCreate): Promise<SignalChain> {
    return api.post<SignalChain>('/signal-chains', data);
  },

  /**
   * List signal chains with filtering, search, and pagination.
   */
  list(params?: SignalChainListParams): Promise<SignalChainListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.set('search', params.search);
    if (params?.platform) searchParams.set('platform', params.platform);
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    if (params?.sort_by) searchParams.set('sort_by', params.sort_by);
    if (params?.sort_order) searchParams.set('sort_order', params.sort_order);
    const query = searchParams.toString();
    return api.get(`/signal-chains${query ? `?${query}` : ''}`);
  },

  /**
   * Get a single signal chain by ID with all blocks.
   */
  get(id: string): Promise<SignalChain> {
    return api.get<SignalChain>(`/signal-chains/${id}`);
  },

  /**
   * Update a signal chain (partial update or full block replacement).
   */
  update(id: string, data: SignalChainUpdate): Promise<SignalChain> {
    return api.patch<SignalChain>(`/signal-chains/${id}`, data);
  },

  /**
   * Delete a signal chain.
   */
  delete(id: string): Promise<void> {
    return api.delete<void>(`/signal-chains/${id}`);
  },

  /**
   * Validate signal chain grammar rules.
   */
  validate(id: string): Promise<SignalChainValidationResponse> {
    return api.post<SignalChainValidationResponse>(`/signal-chains/${id}/validate`);
  },

  /**
   * Get guidance for building a signal chain.
   * Returns valid next gear types and guidance message based on current composition.
   * This is a stateless computation - no auth required.
   */
  guidance(request: SignalChainGuidanceRequest): Promise<SignalChainGuidanceResponse> {
    return api.post<SignalChainGuidanceResponse>('/signal-chains/guidance', request);
  },
};


// =============================================================================
// Signal Chain Group Types
// =============================================================================

/** Limits for signal chain groups (matches backend domain) */
export const SIGNAL_CHAIN_GROUP_LIMITS = {
  MAX_DI_TRACKS: 3,
  MAX_AMPS: 3,
  MAX_IRS: 3,
} as const;

/** DI track item in a group response */
export interface GroupDITrackItem {
  id: string;
  di_track_id: string;
  position: number;
  title: string | null;
}

/** Amp item in a group response */
export interface GroupAmpItem {
  id: string;
  user_gear_id: string;
  position: number;
  display_name: string | null;
  is_full_rig: boolean;
}

/** IR item in a group response */
export interface GroupIRItem {
  id: string;
  user_gear_id: string;
  position: number;
  display_name: string | null;
}

/** Request to create a signal chain group */
export interface SignalChainGroupCreate {
  name: string;
  platform?: SignalChainPlatform;
  di_track_ids: string[];
  amp_user_gear_ids: string[];
  ir_user_gear_ids?: string[];
}

/** Full group response with all details */
export interface SignalChainGroupResponse {
  id: string;
  name: string;
  platform: string;
  user_id: string;
  di_tracks: GroupDITrackItem[];
  amps: GroupAmpItem[];
  irs: GroupIRItem[];
  chains: SignalChainListItem[];
  chain_count: number;
  created_at: string;
  updated_at: string;
}

/** Group item in list responses */
export interface SignalChainGroupListItem {
  id: string;
  name: string;
  platform: string;
  di_track_count: number;
  amp_count: number;
  ir_count: number;
  chain_count: number;
  created_at: string;
  updated_at: string;
}

/** Paginated group list response */
export interface SignalChainGroupListResponse {
  groups: SignalChainGroupListItem[];
  total: number;
  page: number;
  page_size: number;
}

/** Rebuild response */
export interface SignalChainGroupRebuildResponse {
  group_id: string;
  chains_deleted: number;
  chains_created: number;
  chains: SignalChainListItem[];
}

/** List params for groups */
export interface SignalChainGroupListParams {
  page?: number;
  page_size?: number;
  sort_by?: 'created_at' | 'name' | 'updated_at';
  sort_order?: 'asc' | 'desc';
}
