/**
 * StageColumn - Container for blocks at a specific signal chain stage.
 *
 * Displays a column with:
 * - Stage header with title and accent color
 * - List of blocks (DI, Pedal, Amp, Cab, or Post-Effect)
 * - Add button to add new blocks
 * - Empty state when no blocks
 * - Visual states (active, inactive, complete) for UX guidance
 *
 * Supports drag-and-drop reordering when integrated with dnd-kit.
 */
import type { ReactNode } from 'react';
import { Plus, Music, Speaker, Box, Sparkles, Clock, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { BlockStage } from './types';

/** Visual state for column to guide users through the signal chain flow */
export type ColumnState = 'active' | 'inactive' | 'complete';

interface StageColumnProps {
  /** Stage type determines styling and icons */
  stage: BlockStage;
  /** Display title for the column */
  title: string;
  /** Number of blocks in this column */
  blockCount: number;
  /** Column content (blocks rendered by parent) */
  children?: ReactNode;
  /** Callback when add button is clicked */
  onAddClick?: () => void;
  /** Whether adding is disabled (e.g., at max blocks) */
  addDisabled?: boolean;
  /** Custom add button label */
  addLabel?: string;
  /** Visual state for column highlighting (active, inactive, complete) */
  columnState?: ColumnState;
  /** Custom empty state message (overrides default) */
  emptyMessage?: string;
  /** Additional CSS classes */
  className?: string;
}

/** Stage configuration for styling and icons */
const stageConfig: Record<
  BlockStage,
  {
    icon: typeof Music;
    colorVar: string;
    emptyText: string;
    addText: string;
  }
> = {
  di: {
    icon: Music,
    colorVar: '--color-block-di',
    emptyText: 'Upload a DI track to get started',
    addText: 'Add DI Track',
  },
  amp: {
    icon: Speaker,
    colorVar: '--color-block-amp',
    emptyText: 'Add amp models to process your DI',
    addText: 'Add Amp',
  },
  cab: {
    icon: Box,
    colorVar: '--color-block-cab',
    emptyText: 'Add cabinet IRs for your tone',
    addText: 'Add Cabinet',
  },
  effect: {
    icon: Sparkles,
    colorVar: '--color-block-effect',
    emptyText: 'Add pre-amp pedals (optional)',
    addText: 'Add Pedal',
  },
  postEffect: {
    icon: Clock,
    colorVar: '--color-block-post-effect',
    emptyText: 'Add post-amp effects (optional)',
    addText: 'Add Post-FX',
  },
};

export function StageColumn({
  stage,
  title,
  blockCount,
  children,
  onAddClick,
  addDisabled = false,
  addLabel,
  columnState = 'active',
  emptyMessage,
  className,
}: StageColumnProps) {
  const config = stageConfig[stage];
  const Icon = config.icon;
  const isInactive = columnState === 'inactive';
  const isComplete = columnState === 'complete';
  const isActive = columnState === 'active';

  return (
    <div
      className={cn(
        'flex flex-col rounded-lg border bg-card transition-all duration-200',
        'min-w-[280px] lg:min-w-[300px]',
        // Visual states
        isActive && 'border-[var(--color-accent-primary)] ring-2 ring-[var(--color-accent-primary)]/30',
        isComplete && 'border-[var(--color-accent-success)]/50',
        isInactive && 'border-border opacity-60',
        // Default border when no special state
        !isActive && !isComplete && !isInactive && 'border-border',
        className
      )}
    >
      {/* Stage Header */}
      <div
        className={cn(
          'flex items-center justify-between border-b p-4',
          isActive && 'border-[var(--color-accent-primary)]/30 bg-[var(--color-accent-primary)]/5',
          isComplete && 'border-[var(--color-accent-success)]/30 bg-[var(--color-accent-success)]/5',
          !isActive && !isComplete && 'border-border'
        )}
      >
        <div className="flex items-center gap-3">
          {/* Stage icon */}
          <div
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-md',
              isInactive && 'opacity-50'
            )}
            style={{ backgroundColor: `var(${config.colorVar})20` }}
          >
            <Icon
              className="h-4 w-4"
              style={{ color: `var(${config.colorVar})` }}
            />
          </div>
          {/* Title and count */}
          <div>
            <div className="flex items-center gap-2">
              <h3 className={cn(
                'font-medium',
                isInactive ? 'text-muted-foreground' : 'text-foreground'
              )}>
                {title}
              </h3>
              {/* Complete indicator */}
              {isComplete && (
                <CheckCircle2 className="h-4 w-4 text-[var(--color-accent-success)]" />
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {blockCount} {blockCount === 1 ? 'block' : 'blocks'}
            </p>
          </div>
        </div>

        {/* Add button */}
        {onAddClick && (
          <button
            type="button"
            onClick={onAddClick}
            disabled={addDisabled || isInactive}
            className={cn(
              'flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium',
              'transition-colors',
              addDisabled || isInactive
                ? 'cursor-not-allowed text-muted-foreground'
                : 'text-foreground hover:bg-muted'
            )}
            style={
              !addDisabled && !isInactive
                ? { color: `var(${config.colorVar})` }
                : undefined
            }
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">{addLabel || config.addText}</span>
          </button>
        )}
      </div>

      {/* Blocks container */}
      <div className={cn('flex-1 p-4', isInactive && 'pointer-events-none')}>
        {blockCount === 0 ? (
          /* Empty state */
          <div
            className={cn(
              'flex min-h-[120px] flex-col items-center justify-center rounded-lg border border-dashed p-6 text-center',
              isActive && 'border-[var(--color-accent-primary)]/40 bg-[var(--color-accent-primary)]/5',
              isInactive && 'border-border/50',
              !isActive && !isInactive && 'border-border'
            )}
          >
            <Icon className={cn(
              'mb-2 h-8 w-8',
              isInactive ? 'text-muted-foreground/50' : 'text-muted-foreground'
            )} />
            <p className={cn(
              'text-sm',
              isInactive ? 'text-muted-foreground/50' : 'text-muted-foreground'
            )}>
              {emptyMessage || config.emptyText}
            </p>
            {onAddClick && !addDisabled && !isInactive && (
              <button
                type="button"
                onClick={onAddClick}
                className="mt-3 flex items-center gap-1 text-sm font-medium hover:underline"
                style={{ color: `var(${config.colorVar})` }}
              >
                <Plus className="h-4 w-4" />
                {addLabel || config.addText}
              </button>
            )}
          </div>
        ) : (
          /* Block list */
          <div className="space-y-3">{children}</div>
        )}
      </div>
    </div>
  );
}
