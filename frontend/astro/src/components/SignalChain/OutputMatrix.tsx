/**
 * OutputMatrix - Preview of all signal chain combinations.
 *
 * Calculates and displays the Cartesian product of:
 * DI Tracks x Amps x Cabs = Total Segments
 *
 * Features:
 * - Real-time combination count
 * - Preview list with expand/collapse
 * - Estimated video duration
 * - Warning for large matrices
 */
import { useState, useMemo } from 'react';
import { BarChart3, ChevronDown, ChevronUp, Clock, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DIBlock, AmpBlockData, CabBlockData } from './types';

interface OutputMatrixProps {
  /** DI tracks in the signal chain */
  diTracks: DIBlock[];
  /** Amp models in the signal chain */
  amps: AmpBlockData[];
  /** Cabinet models in the signal chain */
  cabs: CabBlockData[];
  /** Average duration per DI track in seconds (for estimation) */
  avgTrackDuration?: number;
  /** Maximum combinations before showing warning */
  warningThreshold?: number;
  /** Additional CSS classes */
  className?: string;
}

interface Combination {
  diTrack: DIBlock;
  amp: AmpBlockData;
  cab: CabBlockData;
}

/** Default time per segment transition in seconds */
const TRANSITION_TIME = 2;

/** Default time for intro/outro in seconds */
const INTRO_OUTRO_TIME = 5;

/**
 * Generate all combinations of DI tracks, amps, and cabs.
 */
function generateCombinations(
  diTracks: DIBlock[],
  amps: AmpBlockData[],
  cabs: CabBlockData[]
): Combination[] {
  const combinations: Combination[] = [];

  for (const diTrack of diTracks) {
    for (const amp of amps) {
      for (const cab of cabs) {
        combinations.push({ diTrack, amp, cab });
      }
    }
  }

  return combinations;
}

/**
 * Estimate total video duration based on combinations.
 */
function estimateDuration(
  combinations: Combination[],
  avgTrackDuration: number
): number {
  if (combinations.length === 0) return 0;

  // Each combination plays the full track
  const totalPlayTime = combinations.length * avgTrackDuration;

  // Add transitions between segments
  const transitionTime = Math.max(0, combinations.length - 1) * TRANSITION_TIME;

  // Add intro and outro
  const totalTime = totalPlayTime + transitionTime + INTRO_OUTRO_TIME;

  return totalTime;
}

/**
 * Format duration in seconds to MM:SS or HH:MM:SS format.
 */
function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

export function OutputMatrix({
  diTracks,
  amps,
  cabs,
  avgTrackDuration,
  warningThreshold = 20,
  className,
}: OutputMatrixProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Calculate combinations
  const combinations = useMemo(
    () => generateCombinations(diTracks, amps, cabs),
    [diTracks, amps, cabs]
  );

  // Calculate average track duration from DI tracks if not provided
  const effectiveAvgDuration = useMemo(() => {
    if (avgTrackDuration) return avgTrackDuration;
    if (diTracks.length === 0) return 30; // Default 30 seconds
    return diTracks.reduce((sum, t) => sum + t.duration, 0) / diTracks.length;
  }, [avgTrackDuration, diTracks]);

  // Estimate total duration
  const estimatedDuration = useMemo(
    () => estimateDuration(combinations, effectiveAvgDuration),
    [combinations, effectiveAvgDuration]
  );

  // Check if we have enough blocks to generate output
  const canGenerate = diTracks.length > 0 && amps.length > 0 && cabs.length > 0;

  // Check if we're over the warning threshold
  const showWarning = combinations.length > warningThreshold;

  // Number of combinations to show in preview
  const previewCount = 5;
  const hasMore = combinations.length > previewCount;
  const displayedCombinations = isExpanded
    ? combinations
    : combinations.slice(0, previewCount);

  if (!canGenerate) {
    return (
      <div
        className={cn(
          'rounded-lg border border-dashed border-border bg-card/50 p-6',
          className
        )}
      >
        <div className="flex items-center gap-3 text-muted-foreground">
          <BarChart3 className="h-5 w-5" />
          <div>
            <h3 className="font-medium text-foreground">Output Preview</h3>
            <p className="text-sm">
              Add at least 1 DI track, 1 amp, and 1 cabinet to see output combinations.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-card overflow-hidden',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-3">
        <div className="flex items-center gap-3">
          <BarChart3 className="h-5 w-5 text-foreground" />
          <div>
            <h3 className="font-medium text-foreground">Output Preview</h3>
            <p className="text-sm text-muted-foreground">
              {combinations.length} segment{combinations.length !== 1 ? 's' : ''} will be
              generated
            </p>
          </div>
        </div>

        {/* Estimated duration */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="h-4 w-4" />
          <span>~{formatDuration(estimatedDuration)}</span>
        </div>
      </div>

      {/* Warning for large matrices */}
      {showWarning && (
        <div className="flex items-center gap-2 border-b border-amber-500/20 bg-amber-500/10 px-4 py-2 text-sm text-amber-500">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>
            Large number of combinations. Processing may take a while.
          </span>
        </div>
      )}

      {/* Combination list */}
      <div className="p-4">
        <div className="space-y-2">
          {displayedCombinations.map((combo, index) => (
            <div
              key={`${combo.diTrack.id}-${combo.amp.id}-${combo.cab.id}`}
              className="flex items-center gap-2 text-sm"
            >
              <span className="w-6 text-right text-muted-foreground">
                {index + 1}.
              </span>
              <span className="text-[var(--color-block-di)]">
                {combo.diTrack.filename}
              </span>
              <span className="text-muted-foreground">→</span>
              <span className="text-[var(--color-block-amp)]">
                {combo.amp.tone.title}
              </span>
              <span className="text-muted-foreground">→</span>
              <span className="text-[var(--color-block-cab)]">
                {combo.cab.tone.title}
              </span>
            </div>
          ))}
        </div>

        {/* Expand/collapse button */}
        {hasMore && (
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="mt-3 flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            {isExpanded ? (
              <>
                <ChevronUp className="h-4 w-4" />
                Show less
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4" />
                Show all {combinations.length} combinations
              </>
            )}
          </button>
        )}
      </div>

      {/* Summary footer */}
      <div className="border-t border-border bg-muted/20 px-4 py-3">
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span>
            <strong className="text-foreground">{diTracks.length}</strong> DI
            track{diTracks.length !== 1 ? 's' : ''}
          </span>
          <span>×</span>
          <span>
            <strong className="text-foreground">{amps.length}</strong> amp
            {amps.length !== 1 ? 's' : ''}
          </span>
          <span>×</span>
          <span>
            <strong className="text-foreground">{cabs.length}</strong> cabinet
            {cabs.length !== 1 ? 's' : ''}
          </span>
          <span>=</span>
          <span>
            <strong className="text-foreground">{combinations.length}</strong>{' '}
            segment{combinations.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
    </div>
  );
}
