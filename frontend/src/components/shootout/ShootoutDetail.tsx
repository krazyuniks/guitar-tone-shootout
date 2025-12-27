/**
 * ShootoutDetail - Main component for the shootout detail page.
 * Displays video player, segment navigation, signal chain, and metadata.
 */

import { useQuery } from '@tanstack/react-query';
import { useState, useCallback, useEffect } from 'react';
import { api, type ShootoutDetail as ShootoutDetailType, type ToneSelection } from '@/lib/api';
import { QueryProvider } from '@/lib/query';
import { VideoPlayer } from './VideoPlayer';
import { SignalChainVisual } from './SignalChainVisual';
import { cn } from '@/lib/utils';

interface ShootoutDetailInnerProps {
  shootoutId: string;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);
  const diffMonths = Math.floor(diffDays / 30);

  if (diffMonths > 0) {
    return diffMonths === 1 ? '1 month ago' : `${diffMonths} months ago`;
  }
  if (diffWeeks > 0) {
    return diffWeeks === 1 ? '1 week ago' : `${diffWeeks} weeks ago`;
  }
  if (diffDays > 0) {
    return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
  }
  if (diffHours > 0) {
    return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
  }
  if (diffMinutes > 0) {
    return diffMinutes === 1 ? '1 minute ago' : `${diffMinutes} minutes ago`;
  }
  return 'Just now';
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Segment button component
interface SegmentButtonProps {
  segment: ToneSelection;
  isActive: boolean;
  onClick: () => void;
}

function SegmentButton({ segment, isActive, onClick }: SegmentButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex-shrink-0 min-w-[120px] px-4 py-3 rounded-lg border transition-all text-left',
        isActive
          ? 'bg-amber-500/20 border-amber-500 text-amber-400'
          : 'bg-[var(--color-bg-surface)] border-[var(--border)] text-[var(--color-text-secondary)] hover:border-amber-500/50 hover:text-[var(--color-text-primary)]'
      )}
    >
      <div className="font-medium text-sm line-clamp-1">
        {segment.display_name ?? segment.tone_title}
      </div>
      <div className="text-xs text-[var(--color-text-muted)] mt-1">
        {formatTime((segment.start_ms ?? 0) / 1000)}
      </div>
    </button>
  );
}

function ShootoutDetailInner({ shootoutId }: ShootoutDetailInnerProps) {
  const [activeSegmentIndex, setActiveSegmentIndex] = useState(0);

  // Fetch shootout data
  const { data: shootout, isLoading, error } = useQuery({
    queryKey: ['shootout', shootoutId],
    queryFn: () => api.get<ShootoutDetailType>(`/shootouts/${shootoutId}`),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Handle segment click - jump to that segment in the video
  const handleSegmentClick = useCallback((_segment: ToneSelection, index: number) => {
    setActiveSegmentIndex(index);
    // In a real implementation, we would control the video player here
    // For now, we just update the active segment
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8 animate-pulse">
        <div className="h-8 bg-[var(--color-bg-elevated)] rounded w-24 mb-6" />
        <div className="aspect-video bg-[var(--color-bg-elevated)] rounded-lg mb-6" />
        <div className="h-8 bg-[var(--color-bg-elevated)] rounded w-2/3 mb-4" />
        <div className="h-4 bg-[var(--color-bg-elevated)] rounded w-1/3 mb-8" />
        <div className="flex gap-3">
          <div className="h-20 w-32 bg-[var(--color-bg-elevated)] rounded" />
          <div className="h-20 w-32 bg-[var(--color-bg-elevated)] rounded" />
          <div className="h-20 w-32 bg-[var(--color-bg-elevated)] rounded" />
        </div>
      </div>
    );
  }

  // Error state
  if (error || !shootout) {
    return (
      <div className="container mx-auto px-4 py-16">
        <div className="text-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="w-16 h-16 mx-auto mb-4 text-red-500"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
            Shootout Not Found
          </h2>
          <p className="text-[var(--color-text-secondary)] mb-6">
            This shootout may have been removed or the link is incorrect.
          </p>
          <a
            href="/shootouts"
            className="inline-flex items-center gap-2 text-amber-500 hover:text-amber-400 transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-5 h-5"
            >
              <path
                fillRule="evenodd"
                d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
                clipRule="evenodd"
              />
            </svg>
            Back to Browse
          </a>
        </div>
      </div>
    );
  }

  const segments = shootout.tone_selections.sort((a, b) => a.position - b.position);
  const activeSegment = segments[activeSegmentIndex] ?? segments[0];

  return (
    <div className="container mx-auto px-4 py-6 max-w-6xl">
      {/* Back link */}
      <a
        href="/shootouts"
        className="inline-flex items-center gap-2 text-[var(--color-text-secondary)] hover:text-amber-400 transition-colors mb-6"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="w-5 h-5"
        >
          <path
            fillRule="evenodd"
            d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
            clipRule="evenodd"
          />
        </svg>
        Back to Browse
      </a>

      {/* Video Player */}
      {shootout.is_processed && shootout.output_path ? (
        <VideoPlayer
          src={shootout.output_path}
          segments={segments}
          className="mb-6"
        />
      ) : (
        <div className="aspect-video bg-[var(--color-bg-surface)] rounded-lg flex items-center justify-center mb-6 border border-[var(--border)]">
          <div className="text-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="w-16 h-16 mx-auto mb-4 text-[var(--color-text-muted)]"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h3 className="text-lg font-medium text-[var(--color-text-primary)] mb-2">
              Processing in Progress
            </h3>
            <p className="text-sm text-[var(--color-text-secondary)]">
              This shootout is still being rendered. Check back soon!
            </p>
          </div>
        </div>
      )}

      {/* Title and metadata */}
      <div className="mb-6">
        <h1 className="text-2xl md:text-3xl font-bold text-[var(--color-text-primary)] mb-2">
          {shootout.name}
        </h1>
        <div className="flex flex-wrap items-center gap-3 text-sm text-[var(--color-text-secondary)]">
          <span>{segments.length} {segments.length === 1 ? 'tone' : 'tones'}</span>
          <span className="text-[var(--color-text-muted)]">-</span>
          <span>{formatRelativeTime(shootout.created_at)}</span>
          {shootout.guitar && (
            <>
              <span className="text-[var(--color-text-muted)]">-</span>
              <span>{shootout.guitar}</span>
            </>
          )}
          {shootout.pickup && (
            <>
              <span className="text-[var(--color-text-muted)]">-</span>
              <span>{shootout.pickup}</span>
            </>
          )}
        </div>
      </div>

      {/* Segments */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4 flex items-center gap-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="w-5 h-5 text-amber-500"
          >
            <path
              fillRule="evenodd"
              d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm14.024-.983a1.125 1.125 0 010 1.966l-5.603 3.113A1.125 1.125 0 019 15.113V8.887c0-.857.921-1.4 1.671-.983l5.603 3.113z"
              clipRule="evenodd"
            />
          </svg>
          Segments
        </h2>
        <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-[var(--color-bg-elevated)]">
          {segments.map((segment, index) => (
            <SegmentButton
              key={segment.id}
              segment={segment}
              isActive={index === activeSegmentIndex}
              onClick={() => handleSegmentClick(segment, index)}
            />
          ))}
        </div>
      </div>

      {/* Signal Chain for active segment */}
      {activeSegment && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4 flex items-center gap-2">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-5 h-5 text-amber-500"
            >
              <path
                fillRule="evenodd"
                d="M14.615 1.595a.75.75 0 01.359.852L12.982 9.75h7.268a.75.75 0 01.548 1.262l-10.5 11.25a.75.75 0 01-1.272-.71l1.992-7.302H3.75a.75.75 0 01-.548-1.262l10.5-11.25a.75.75 0 01.913-.143z"
                clipRule="evenodd"
              />
            </svg>
            Signal Chain: {activeSegment.display_name ?? activeSegment.tone_title}
          </h2>
          <div className="bg-[var(--color-bg-surface)] rounded-lg border border-[var(--border)] p-4 overflow-x-auto">
            <SignalChainVisual segment={activeSegment} />
          </div>
        </div>
      )}

      {/* Description */}
      {(shootout.description || shootout.di_track_description) && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4 flex items-center gap-2">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-5 h-5 text-amber-500"
            >
              <path
                fillRule="evenodd"
                d="M4.125 3C3.089 3 2.25 3.84 2.25 4.875V18a3 3 0 003 3h15a3 3 0 01-3-3V4.875C17.25 3.839 16.41 3 15.375 3H4.125zM12 9.75a.75.75 0 000 1.5h1.5a.75.75 0 000-1.5H12zm-.75-2.25a.75.75 0 01.75-.75h1.5a.75.75 0 010 1.5H12a.75.75 0 01-.75-.75zM6 12.75a.75.75 0 000 1.5h7.5a.75.75 0 000-1.5H6zm-.75 3.75a.75.75 0 01.75-.75h7.5a.75.75 0 010 1.5H6a.75.75 0 01-.75-.75zM6 6.75a.75.75 0 00-.75.75v3c0 .414.336.75.75.75h3a.75.75 0 00.75-.75v-3A.75.75 0 009 6.75H6z"
                clipRule="evenodd"
              />
            </svg>
            Description
          </h2>
          <div className="bg-[var(--color-bg-surface)] rounded-lg border border-[var(--border)] p-4">
            {shootout.description && (
              <p className="text-[var(--color-text-secondary)] whitespace-pre-wrap">
                {shootout.description}
              </p>
            )}
            {shootout.di_track_description && (
              <div className={shootout.description ? 'mt-4 pt-4 border-t border-[var(--border)]' : ''}>
                <h3 className="text-sm font-medium text-[var(--color-text-primary)] mb-2">
                  DI Recording Notes
                </h3>
                <p className="text-sm text-[var(--color-text-muted)]">
                  {shootout.di_track_description}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tone details section */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4 flex items-center gap-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="w-5 h-5 text-amber-500"
          >
            <path
              fillRule="evenodd"
              d="M11.078 2.25c-.917 0-1.699.663-1.85 1.567L9.05 4.889c-.02.12-.115.26-.297.348a7.493 7.493 0 00-.986.57c-.166.115-.334.126-.45.083L6.3 5.508a1.875 1.875 0 00-2.282.819l-.922 1.597a1.875 1.875 0 00.432 2.385l.84.692c.095.078.17.229.154.43a7.598 7.598 0 000 1.139c.015.2-.059.352-.153.43l-.841.692a1.875 1.875 0 00-.432 2.385l.922 1.597a1.875 1.875 0 002.282.818l1.019-.382c.115-.043.283-.031.45.082.312.214.641.405.985.57.182.088.277.228.297.35l.178 1.071c.151.904.933 1.567 1.85 1.567h1.844c.916 0 1.699-.663 1.85-1.567l.178-1.072c.02-.12.114-.26.297-.349.344-.165.673-.356.985-.57.167-.114.335-.125.45-.082l1.02.382a1.875 1.875 0 002.28-.819l.923-1.597a1.875 1.875 0 00-.432-2.385l-.84-.692c-.095-.078-.17-.229-.154-.43a7.614 7.614 0 000-1.139c-.016-.2.059-.352.153-.43l.84-.692c.708-.582.891-1.59.433-2.385l-.922-1.597a1.875 1.875 0 00-2.282-.818l-1.02.382c-.114.043-.282.031-.449-.083a7.49 7.49 0 00-.985-.57c-.183-.087-.277-.227-.297-.348l-.179-1.072a1.875 1.875 0 00-1.85-1.567h-1.843zM12 15.75a3.75 3.75 0 100-7.5 3.75 3.75 0 000 7.5z"
              clipRule="evenodd"
            />
          </svg>
          All Tones in This Shootout
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {segments.map((segment, index) => (
            <div
              key={segment.id}
              className={cn(
                'bg-[var(--color-bg-surface)] rounded-lg border p-4 transition-all cursor-pointer',
                index === activeSegmentIndex
                  ? 'border-amber-500 shadow-lg shadow-amber-500/10'
                  : 'border-[var(--border)] hover:border-amber-500/50'
              )}
              onClick={() => handleSegmentClick(segment, index)}
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-medium text-[var(--color-text-primary)]">
                  {segment.display_name ?? segment.tone_title}
                </h3>
                <span className={cn(
                  'text-xs px-2 py-0.5 rounded-full',
                  segment.gear_type === 'amp'
                    ? 'bg-amber-500/20 text-amber-400'
                    : segment.gear_type === 'pedal'
                      ? 'bg-purple-500/20 text-purple-400'
                      : 'bg-blue-500/20 text-blue-400'
                )}>
                  {segment.gear_type}
                </span>
              </div>
              <div className="text-sm text-[var(--color-text-secondary)] mb-2">
                {segment.model_name}
              </div>
              <div className="text-xs text-[var(--color-text-muted)]">
                {segment.model_size} model
                {segment.start_ms !== null && ` - ${formatTime(segment.start_ms / 1000)}`}
              </div>
              {segment.description && (
                <p className="text-xs text-[var(--color-text-muted)] mt-2 line-clamp-2">
                  {segment.description}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Processing metadata (if available) */}
      {shootout.processing_metadata && (
        <div className="text-xs text-[var(--color-text-muted)] mt-8 pt-4 border-t border-[var(--border)]">
          <div className="flex flex-wrap gap-4">
            <span>Processed: {formatDate(shootout.processing_metadata.processed_at)}</span>
            <span>Pipeline v{shootout.processing_metadata.pipeline_version}</span>
            {shootout.processing_metadata.processing_duration_seconds && (
              <span>Render time: {Math.round(shootout.processing_metadata.processing_duration_seconds)}s</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Wrapper with QueryProvider
interface ShootoutDetailProps {
  shootoutId: string;
}

export function ShootoutDetailComponent({ shootoutId }: ShootoutDetailProps) {
  return (
    <QueryProvider>
      <ShootoutDetailInner shootoutId={shootoutId} />
    </QueryProvider>
  );
}

// UUID validation regex
const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Component that extracts ID from URL - for client-side routing
function ShootoutPageClient() {
  const [shootoutId, setShootoutId] = useState<string | null>(null);
  const [isInvalidId, setIsInvalidId] = useState(false);

  useEffect(() => {
    // Extract ID from URL path: /shootout/{id}
    const pathParts = window.location.pathname.split('/');
    const idFromPath = pathParts[pathParts.length - 1];

    if (idFromPath && uuidRegex.test(idFromPath)) {
      setShootoutId(idFromPath);
    } else {
      setIsInvalidId(true);
    }
  }, []);

  if (isInvalidId) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="w-16 h-16 mx-auto mb-4 text-red-500"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
          />
        </svg>
        <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
          Invalid Shootout ID
        </h2>
        <p className="text-[var(--color-text-secondary)] mb-6">
          The shootout ID in the URL is not valid.
        </p>
        <a
          href="/shootouts"
          className="inline-flex items-center gap-2 text-amber-500 hover:text-amber-400 transition-colors"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5"
          >
            <path
              fillRule="evenodd"
              d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
              clipRule="evenodd"
            />
          </svg>
          Back to Browse
        </a>
      </div>
    );
  }

  if (!shootoutId) {
    // Loading state while extracting ID from URL
    return (
      <div className="container mx-auto px-4 py-8 animate-pulse">
        <div className="h-8 bg-[var(--color-bg-elevated)] rounded w-24 mb-6" />
        <div className="aspect-video bg-[var(--color-bg-elevated)] rounded-lg mb-6" />
        <div className="h-8 bg-[var(--color-bg-elevated)] rounded w-2/3 mb-4" />
        <div className="h-4 bg-[var(--color-bg-elevated)] rounded w-1/3 mb-8" />
      </div>
    );
  }

  return <ShootoutDetailInner shootoutId={shootoutId} />;
}

// Wrapper with QueryProvider that handles URL extraction
export function ShootoutDetailPage() {
  return (
    <QueryProvider>
      <ShootoutPageClient />
    </QueryProvider>
  );
}

export default ShootoutDetailComponent;
