/**
 * CabinetBlock - Signal chain block for cabinet/IR tone models.
 *
 * Displays cabinet/IR model metadata from Tone 3000 including:
 * - Model title and description
 * - Make/manufacturer info
 * - Platform (IR, NAM, AIDA-X, etc.)
 * - Creator and ratings
 *
 * Uses green accent color (--color-block-cab) from design tokens.
 */
import { X, Box, Star } from 'lucide-react';
import type { Tone, Platform } from '@/lib/api';
import { cn } from '@/lib/utils';

interface CabinetBlockProps {
  /** The tone model data from Tone 3000 */
  tone: Tone;
  /** Callback when the block is removed */
  onRemove?: () => void;
  /** Optional click handler for the block */
  onClick?: () => void;
  /** Whether the block is selected/active */
  isSelected?: boolean;
  /** Additional CSS classes */
  className?: string;
}

const platformLabels: Record<Platform, string> = {
  nam: 'NAM',
  ir: 'IR',
  'aida-x': 'AIDA-X',
};

const platformColors: Record<Platform, string> = {
  nam: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  ir: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'aida-x': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

export function CabinetBlock({
  tone,
  onRemove,
  onClick,
  isSelected = false,
  className,
}: CabinetBlockProps) {
  // Extract make name if available
  const makeName = tone.makes.length > 0 ? tone.makes[0].name : null;

  return (
    <div
      className={cn(
        'relative rounded-lg border bg-card p-4 transition-all duration-200',
        // Green accent for cabinet/IR blocks
        isSelected
          ? 'border-green-500 ring-1 ring-green-500/50'
          : 'border-border hover:border-green-500/50',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {/* Remove button */}
      {onRemove && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="absolute right-2 top-2 rounded-full p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
          aria-label={`Remove ${tone.title}`}
        >
          <X className="h-4 w-4" />
        </button>
      )}

      {/* Block type indicator */}
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-green-500/20">
          <Box className="h-4 w-4 text-green-500" />
        </div>
        <span className="text-xs font-semibold uppercase tracking-wider text-green-500">
          Cabinet
        </span>
      </div>

      {/* Model info */}
      <div className="space-y-2">
        {/* Title */}
        <h4 className="truncate font-medium text-foreground pr-6">{tone.title}</h4>

        {/* Make and model info */}
        {makeName && (
          <p className="text-sm text-muted-foreground">{makeName}</p>
        )}

        {/* Metadata row */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Platform badge */}
          <span
            className={cn(
              'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
              platformColors[tone.platform]
            )}
          >
            {platformLabels[tone.platform]}
          </span>

          {/* Gear type */}
          <span className="text-xs capitalize text-muted-foreground">
            {tone.gear.replace('-', ' ')}
          </span>

          {/* Download count as a rating indicator */}
          {tone.downloads_count > 0 && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Star className="h-3 w-3" />
              {tone.downloads_count.toLocaleString()}
            </span>
          )}
        </div>

        {/* Tags */}
        {tone.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {tone.tags.slice(0, 3).map((tag) => (
              <span
                key={tag.id}
                className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
              >
                {tag.name}
              </span>
            ))}
            {tone.tags.length > 3 && (
              <span className="text-xs text-muted-foreground">
                +{tone.tags.length - 3} more
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
