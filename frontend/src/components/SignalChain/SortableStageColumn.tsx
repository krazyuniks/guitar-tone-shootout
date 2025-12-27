/**
 * SortableStageColumn - Stage column with drag-and-drop sorting.
 *
 * Wraps StageColumn with dnd-kit DndContext and SortableContext to enable
 * reordering of blocks within the column.
 *
 * Features:
 * - Vertical list sorting strategy
 * - Keyboard accessible drag-and-drop
 * - Touch support for mobile
 * - Collision detection with closestCenter algorithm
 */
import type { ReactNode } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { StageColumn } from './StageColumn';
import type { BlockStage } from './types';

interface SortableStageColumnProps<T extends { id: string }> {
  /** Stage type determines styling and icons */
  stage: BlockStage;
  /** Display title for the column */
  title: string;
  /** Array of blocks in this column */
  items: T[];
  /** Callback when blocks are reordered */
  onReorder: (items: T[]) => void;
  /** Render function for each block */
  renderItem: (item: T, index: number) => ReactNode;
  /** Callback when add button is clicked */
  onAddClick?: () => void;
  /** Whether adding is disabled (e.g., at max blocks) */
  addDisabled?: boolean;
  /** Custom add button label */
  addLabel?: string;
  /** Additional CSS classes */
  className?: string;
}

export function SortableStageColumn<T extends { id: string }>({
  stage,
  title,
  items,
  onReorder,
  renderItem,
  onAddClick,
  addDisabled,
  addLabel,
  className,
}: SortableStageColumnProps<T>) {
  // Configure sensors for mouse, touch, and keyboard
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        // Require 5px movement before starting drag (prevents accidental drags)
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = items.findIndex((item) => item.id === active.id);
      const newIndex = items.findIndex((item) => item.id === over.id);

      if (oldIndex !== -1 && newIndex !== -1) {
        const reordered = arrayMove(items, oldIndex, newIndex);
        onReorder(reordered);
      }
    }
  };

  const itemIds = items.map((item) => item.id);

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={itemIds}
        strategy={verticalListSortingStrategy}
      >
        <StageColumn
          stage={stage}
          title={title}
          blockCount={items.length}
          onAddClick={onAddClick}
          addDisabled={addDisabled}
          addLabel={addLabel}
          className={className}
        >
          {items.map((item, index) => renderItem(item, index))}
        </StageColumn>
      </SortableContext>
    </DndContext>
  );
}
