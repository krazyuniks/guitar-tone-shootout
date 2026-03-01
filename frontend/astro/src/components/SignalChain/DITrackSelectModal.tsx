/**
 * DITrackSelectModal - Modal for selecting DI tracks in the signal chain builder.
 *
 * Features:
 * - List all DI tracks (user + system)
 * - Search/filter by title
 * - Display track metadata (duration, sample rate, guitar)
 * - Single-click selection closes modal
 */
import { useState, useMemo, useEffect, useCallback } from 'react';
import { Search, X, Loader2, Music } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { diTrackApi, type DITrackListItem } from '@/lib/api';

interface DITrackSelectModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Callback when a track is selected */
  onSelect: (track: DITrackListItem) => void;
  /** Modal title */
  title?: string;
}

/** Format duration in seconds to MM:SS */
function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/** Format sample rate with kHz suffix */
function formatSampleRate(hz: number): string {
  return `${(hz / 1000).toFixed(1)} kHz`;
}

export function DITrackSelectModal({
  isOpen,
  onClose,
  onSelect,
  title = 'Select DI Track',
}: DITrackSelectModalProps) {
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch DI tracks (user's tracks)
  const userTracksQuery = useQuery({
    queryKey: ['di-tracks', 'user'],
    queryFn: () => diTrackApi.list({ pageSize: 100 }),
    enabled: isOpen,
    staleTime: 30000,
  });

  // Fetch system tracks (available to all users)
  const systemTracksQuery = useQuery({
    queryKey: ['di-tracks', 'system'],
    queryFn: () =>
      // The API uses system_only query param via URLSearchParams
      fetch('/api/di-tracks?page=1&page_size=100&system_only=true', {
        credentials: 'include',
      }).then((res) => {
        if (!res.ok) throw new Error('Failed to fetch system tracks');
        return res.json();
      }),
    enabled: isOpen,
    staleTime: 30000,
  });

  const isLoading = userTracksQuery.isLoading || systemTracksQuery.isLoading;
  const error = userTracksQuery.error || systemTracksQuery.error;

  // Combine and deduplicate tracks
  const allTracks = useMemo(() => {
    const userTracks = userTracksQuery.data?.di_tracks ?? [];
    const systemTracks = systemTracksQuery.data?.di_tracks ?? [];

    // Combine, with user tracks first, then system tracks
    const combined = [...userTracks];
    const userIds = new Set(userTracks.map((t: DITrackListItem) => t.id));

    for (const track of systemTracks) {
      if (!userIds.has(track.id)) {
        combined.push(track);
      }
    }

    return combined;
  }, [userTracksQuery.data, systemTracksQuery.data]);

  // Filter tracks by search query
  const filteredTracks = useMemo(() => {
    if (!searchQuery.trim()) return allTracks;

    const query = searchQuery.toLowerCase();
    return allTracks.filter((track: DITrackListItem) => {
      const titleMatch = track.title.toLowerCase().includes(query);
      const guitarMatch = track.guitar?.toLowerCase().includes(query);
      const descMatch = track.description?.toLowerCase().includes(query);
      return titleMatch || guitarMatch || descMatch;
    });
  }, [allTracks, searchQuery]);

  // Handle track selection
  const handleSelect = useCallback(
    (track: DITrackListItem) => {
      onSelect(track);
      onClose();
    },
    [onSelect, onClose]
  );

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="relative z-10 flex max-h-[90vh] w-full max-w-2xl flex-col rounded-lg border border-border bg-card shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-lg font-semibold text-foreground">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Search */}
        <div className="border-b border-border px-6 py-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search DI tracks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm focus:border-[var(--color-block-di)] focus:outline-none focus:ring-1 focus:ring-[var(--color-block-di)]"
              autoFocus
            />
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted-foreground">
              <p className="text-sm">Failed to load DI tracks</p>
            </div>
          ) : filteredTracks.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center gap-3 text-muted-foreground">
              <Music className="h-12 w-12 text-[var(--color-block-di)]" />
              <p className="text-sm">
                {searchQuery ? 'No matching tracks found' : 'No DI tracks available'}
              </p>
              {!searchQuery && (
                <a
                  href="/library/di-tracks"
                  className="text-sm text-[var(--color-accent-primary)] hover:underline"
                >
                  Upload a DI track
                </a>
              )}
            </div>
          ) : (
            <div className="divide-y divide-border">
              {filteredTracks.map((track: DITrackListItem) => (
                <button
                  key={track.id}
                  type="button"
                  onClick={() => handleSelect(track)}
                  className="flex w-full items-start gap-4 px-6 py-4 text-left transition-colors hover:bg-muted/50"
                >
                  {/* Track icon */}
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--color-block-di)]/20">
                    <Music className="h-5 w-5 text-[var(--color-block-di)]" />
                  </div>

                  {/* Track info */}
                  <div className="min-w-0 flex-1">
                    <h4 className="truncate font-medium text-foreground">
                      {track.title}
                    </h4>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      {formatDuration(track.duration_seconds)} ·{' '}
                      {formatSampleRate(track.sample_rate)}
                      {track.guitar && ` · ${track.guitar}`}
                    </p>
                    {track.description && (
                      <p className="mt-1 truncate text-sm text-muted-foreground/70">
                        {track.description}
                      </p>
                    )}
                  </div>

                  {/* System track badge */}
                  {track.is_system_track && (
                    <span className="shrink-0 rounded-full bg-[var(--color-block-di)]/20 px-2 py-0.5 text-xs font-medium text-[var(--color-block-di)]">
                      System
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border px-6 py-3">
          <p className="text-sm text-muted-foreground">
            {filteredTracks.length} track{filteredTracks.length !== 1 ? 's' : ''} available
          </p>
        </div>
      </div>
    </div>
  );
}
