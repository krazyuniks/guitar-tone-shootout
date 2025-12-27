/**
 * StageColumn - Container for blocks at a specific signal chain stage.
 *
 * Displays a column with:
 * - Stage header with title and accent color
 * - List of blocks (DI, Amp, Cab, or Effect)
 * - Add button to add new blocks
 * - Empty state when no blocks
 *
 * Supports drag-and-drop reordering when integrated with dnd-kit.
 */
import type { ReactNode } from 'react';
import { Plus, Music, Speaker, Box, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { BlockStage } from './types';

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
    emptyText: 'Add effects (optional)',
    addText: 'Add Effect',
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
  className,
}: StageColumnProps) {
  const config = stageConfig[stage];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        'flex flex-col rounded-lg border border-border bg-card',
        'min-w-[280px] lg:min-w-[300px]',
        className
      )}
    >
      {/* Stage Header */}
      <div className="flex items-center justify-between border-b border-border p-4">
        <div className="flex items-center gap-3">
          {/* Stage icon */}
          <div
            className="flex h-8 w-8 items-center justify-center rounded-md"
            style={{ backgroundColor: `var(${config.colorVar})20` }}
          >
            <Icon
              className="h-4 w-4"
              style={{ color: `var(${config.colorVar})` }}
            />
          </div>
          {/* Title and count */}
          <div>
            <h3 className="font-medium text-foreground">{title}</h3>
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
            disabled={addDisabled}
            className={cn(
              'flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium',
              'transition-colors',
              addDisabled
                ? 'cursor-not-allowed text-muted-foreground'
                : 'text-foreground hover:bg-muted'
            )}
            style={
              !addDisabled
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
      <div className="flex-1 p-4">
        {blockCount === 0 ? (
          /* Empty state */
          <div className="flex min-h-[120px] flex-col items-center justify-center rounded-lg border border-dashed border-border p-6 text-center">
            <Icon className="mb-2 h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{config.emptyText}</p>
            {onAddClick && !addDisabled && (
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
