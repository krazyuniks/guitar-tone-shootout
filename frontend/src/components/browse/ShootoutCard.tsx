/**
 * ShootoutCard - A card component displaying a shootout preview.
 * Shows thumbnail, title, tone count, and time since creation.
 */

import type { ShootoutListItem } from '@/lib/api';
import { cn } from '@/lib/utils';

interface ShootoutCardProps {
  shootout: ShootoutListItem;
  className?: string;
}

/**
 * Format a relative time string (e.g., "2 days ago", "5 hours ago")
 */
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

export function ShootoutCard({ shootout, className }: ShootoutCardProps) {
  const relativeTime = formatRelativeTime(shootout.created_at);

  return (
    <a
      href={`/shootout/${shootout.id}`}
      className={cn(
        'group block rounded-lg overflow-hidden bg-[var(--color-bg-surface)] border border-[var(--border)] transition-all duration-200 hover:border-amber-500/50 hover:shadow-lg hover:shadow-amber-500/10',
        className
      )}
    >
      {/* Thumbnail / Preview */}
      <div className="aspect-video bg-[var(--color-bg-elevated)] relative overflow-hidden">
        {shootout.is_processed && shootout.output_path ? (
          // Video thumbnail would go here - for now show a placeholder
          <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-amber-900/20 to-amber-700/20">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-12 h-12 text-amber-500/60 group-hover:text-amber-500 transition-colors"
            >
              <path
                fillRule="evenodd"
                d="M4.5 5.653c0-1.426 1.529-2.33 2.779-1.643l11.54 6.348c1.295.712 1.295 2.573 0 3.285L7.28 19.991c-1.25.687-2.779-.217-2.779-1.643V5.653z"
                clipRule="evenodd"
              />
            </svg>
          </div>
        ) : (
          // Processing or not ready state
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="w-10 h-10 text-[var(--color-text-muted)] mx-auto mb-2"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-xs text-[var(--color-text-muted)]">Processing...</span>
            </div>
          </div>
        )}

        {/* Tone count badge */}
        <div className="absolute bottom-2 right-2 bg-black/70 backdrop-blur-sm px-2 py-1 rounded text-xs font-medium text-white">
          {shootout.tone_count} {shootout.tone_count === 1 ? 'tone' : 'tones'}
        </div>
      </div>

      {/* Card content */}
      <div className="p-4">
        <h3 className="font-semibold text-[var(--color-text-primary)] line-clamp-2 group-hover:text-amber-400 transition-colors">
          {shootout.name}
        </h3>

        {shootout.description && (
          <p className="mt-1 text-sm text-[var(--color-text-secondary)] line-clamp-2">
            {shootout.description}
          </p>
        )}

        <div className="mt-3 flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
          <span>{relativeTime}</span>
        </div>
      </div>
    </a>
  );
}

export default ShootoutCard;
