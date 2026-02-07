/**
 * BlockCard - Base component for signal chain blocks.
 *
 * Provides consistent styling and structure for all block types:
 * - DI (input tracks)
 * - Amp (NAM/neural amp modelers)
 * - Cab (cabinet/IR blocks)
 * - Effect (pedals/effects)
 *
 * Uses design tokens from global.css for block type colors.
 */
import type { ReactNode } from 'react';
import { GripVertical } from 'lucide-react';
import { cn } from '@/lib/utils';

export type BlockType = 'di' | 'amp' | 'cab' | 'effect';

interface BlockCardProps {
  /** Block type determines accent color */
  type: BlockType;
  /** Icon displayed in the block header */
  icon: ReactNode;
  /** Block title */
  title: string;
  /** Optional subtitle/description */
  subtitle?: string;
  /** Content area for block-specific UI */
  children?: ReactNode;
  /** Show drag handle for reordering */
  showDragHandle?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Drag handle props for dnd-kit integration */
  dragHandleProps?: Record<string, unknown>;
}

/**
 * Maps block types to their CSS custom property color variables.
 * These colors are defined in global.css as --color-block-*.
 */
const blockTypeStyles: Record<BlockType, { accent: string; bg: string; border: string }> = {
  di: {
    accent: 'text-[var(--color-block-di)]',
    bg: 'bg-[var(--color-block-di)]/10',
    border: 'border-[var(--color-block-di)]/30 hover:border-[var(--color-block-di)]/50',
  },
  amp: {
    accent: 'text-[var(--color-block-amp)]',
    bg: 'bg-[var(--color-block-amp)]/10',
    border: 'border-[var(--color-block-amp)]/30 hover:border-[var(--color-block-amp)]/50',
  },
  cab: {
    accent: 'text-[var(--color-block-cab)]',
    bg: 'bg-[var(--color-block-cab)]/10',
    border: 'border-[var(--color-block-cab)]/30 hover:border-[var(--color-block-cab)]/50',
  },
  effect: {
    accent: 'text-[var(--color-block-effect)]',
    bg: 'bg-[var(--color-block-effect)]/10',
    border: 'border-[var(--color-block-effect)]/30 hover:border-[var(--color-block-effect)]/50',
  },
};

export function BlockCard({
  type,
  icon,
  title,
  subtitle,
  children,
  showDragHandle = false,
  className,
  dragHandleProps,
}: BlockCardProps) {
  const styles = blockTypeStyles[type];

  return (
    <div
      className={cn(
        'relative rounded-lg border bg-card transition-colors',
        styles.border,
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-3 p-4">
        {/* Drag handle */}
        {showDragHandle && (
          <button
            type="button"
            className="shrink-0 cursor-grab touch-none rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground active:cursor-grabbing"
            aria-label="Drag to reorder"
            {...dragHandleProps}
          >
            <GripVertical className="h-4 w-4" />
          </button>
        )}

        {/* Icon */}
        <div
          className={cn(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-md',
            styles.bg
          )}
        >
          <span className={styles.accent}>{icon}</span>
        </div>

        {/* Title and subtitle */}
        <div className="min-w-0 flex-1">
          <h4 className="truncate font-medium text-foreground">{title}</h4>
          {subtitle && (
            <p className="truncate text-sm text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </div>

      {/* Content area */}
      {children && (
        <div className="border-t border-border px-4 py-3">{children}</div>
      )}
    </div>
  );
}
