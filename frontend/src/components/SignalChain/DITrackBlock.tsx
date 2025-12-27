/**
 * DITrackBlock - Displays a DI track in the signal chain.
 *
 * Shows:
 * - Waveform visualization (placeholder for now)
 * - Filename
 * - Duration
 * - Sample rate
 *
 * Uses blue accent color (--color-block-di) via BlockCard.
 */
import { Music } from 'lucide-react';
import { BlockCard } from './BlockCard';

interface DITrackBlockProps {
  /** Display name for the track */
  filename: string;
  /** Duration in seconds */
  duration: number;
  /** Sample rate in Hz (e.g., 44100, 48000) */
  sampleRate: number;
  /** Show drag handle for reordering */
  showDragHandle?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Drag handle props for dnd-kit integration */
  dragHandleProps?: Record<string, unknown>;
}

/**
 * Formats duration in seconds to MM:SS format.
 */
function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Formats sample rate with kHz suffix.
 */
function formatSampleRate(hz: number): string {
  return `${(hz / 1000).toFixed(1)} kHz`;
}

/**
 * Waveform visualization placeholder.
 * This will be replaced with actual waveform rendering.
 */
function WaveformPlaceholder() {
  return (
    <div className="flex h-12 items-center justify-center rounded bg-[var(--color-block-di)]/5">
      {/* Placeholder waveform bars */}
      <div className="flex items-end gap-0.5">
        {[0.3, 0.5, 0.8, 0.6, 0.9, 0.4, 0.7, 0.5, 0.8, 0.6, 0.4, 0.7, 0.5, 0.3, 0.6].map(
          (height, i) => (
            <div
              key={i}
              className="w-1 rounded-full bg-[var(--color-block-di)]/40"
              style={{ height: `${height * 100}%` }}
            />
          )
        )}
      </div>
    </div>
  );
}

export function DITrackBlock({
  filename,
  duration,
  sampleRate,
  showDragHandle = false,
  className,
  dragHandleProps,
}: DITrackBlockProps) {
  return (
    <BlockCard
      type="di"
      icon={<Music className="h-5 w-5" />}
      title={filename}
      subtitle="DI Track"
      showDragHandle={showDragHandle}
      dragHandleProps={dragHandleProps}
      className={className}
    >
      <div className="space-y-3">
        {/* Waveform visualization */}
        <WaveformPlaceholder />

        {/* Track info */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="font-medium text-foreground">Duration:</span>
            {formatDuration(duration)}
          </span>
          <span className="flex items-center gap-1">
            <span className="font-medium text-foreground">Sample Rate:</span>
            {formatSampleRate(sampleRate)}
          </span>
        </div>
      </div>
    </BlockCard>
  );
}
