/**
 * SortableBlock - Wrapper component for drag-and-drop sortable blocks.
 *
 * Uses dnd-kit for accessible drag-and-drop functionality with:
 * - Mouse/touch support
 * - Keyboard navigation (Tab, Space, Arrow keys)
 * - Visual feedback during drag operations
 *
 * Wraps any block component to make it sortable within a StageColumn.
 */
import type { ReactNode } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { cn } from '@/lib/utils';

interface SortableBlockProps {
  /** Unique identifier for the sortable item */
  id: string;
  /** The block content to render */
  children: ReactNode;
  /** Additional CSS classes */
  className?: string;
  /** Whether the block is disabled for sorting */
  disabled?: boolean;
}

export function SortableBlock({
  id,
  children,
  className,
  disabled = false,
}: SortableBlockProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id,
    disabled,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'relative',
        // Visual feedback during drag
        isDragging && 'z-50 opacity-50 scale-[1.02]',
        // Smooth transitions
        !isDragging && 'transition-transform duration-200',
        className
      )}
      {...attributes}
      {...listeners}
    >
      {children}
    </div>
  );
}

/**
 * SortableBlockHandle - Dedicated drag handle component.
 *
 * Use this when you want only a specific part of the block to be draggable,
 * rather than the entire block.
 */
interface SortableBlockHandleProps {
  /** Unique identifier for the sortable item */
  id: string;
  /** The handle content (usually an icon) */
  children: ReactNode;
  /** Additional CSS classes */
  className?: string;
  /** Whether the handle is disabled */
  disabled?: boolean;
}

export function SortableBlockHandle({
  id,
  children,
  className,
  disabled = false,
}: SortableBlockHandleProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    isDragging,
  } = useSortable({
    id,
    disabled,
  });

  return (
    <button
      type="button"
      ref={setNodeRef}
      className={cn(
        'cursor-grab touch-none rounded p-1 text-muted-foreground',
        'hover:bg-muted hover:text-foreground',
        'active:cursor-grabbing',
        isDragging && 'cursor-grabbing bg-muted',
        disabled && 'cursor-not-allowed opacity-50',
        className
      )}
      aria-label="Drag to reorder"
      {...attributes}
      {...listeners}
    >
      {children}
    </button>
  );
}
