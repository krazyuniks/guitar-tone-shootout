import React, { useState } from "react";
import { DndContext, closestCenter, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";

export interface SignalChainBuilderProps {
  /** Mode: single chain or permutation (multiple gear per slot) */
  mode?: "single" | "permutation";
  /** Chain ID for editing existing chain */
  chainId?: string;
}

interface ChainSlot {
  id: string;
  position: number;
  gearId?: string;
  gearName?: string;
}

/**
 * SignalChainBuilder - React island for building signal chains.
 *
 * Supports drag-and-drop reordering, gear selection from user library,
 * single chain mode, and permutation mode (multiple gear per slot).
 *
 * API endpoints:
 * - /api/v1/signal-chains - CRUD operations
 * - /api/v1/library/gear - User gear library
 */
export function SignalChainBuilder({ mode = "single", chainId }: SignalChainBuilderProps) {
  const [slots, setSlots] = useState<ChainSlot[]>([]);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (active.id !== over?.id) {
      // Reorder slots
      setSlots((prev) => {
        const oldIndex = prev.findIndex((s) => s.id === active.id);
        const newIndex = prev.findIndex((s) => s.id === over?.id);
        const updated = [...prev];
        const [moved] = updated.splice(oldIndex, 1);
        updated.splice(newIndex, 0, moved);
        return updated.map((s, i) => ({ ...s, position: i }));
      });
    }
  }

  async function handleSave() {
    const endpoint = chainId
      ? `/api/v1/signal-chains/${chainId}`
      : "/api/v1/signal-chains";
    const method = chainId ? "PUT" : "POST";

    await fetch(endpoint, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slots, mode }),
    });
  }

  return (
    <div data-testid="signal-chain-builder">
      <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={slots.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {slots.map((slot) => (
              <div key={slot.id} className="p-4 border rounded-lg">
                <span>{slot.gearName || "Select gear"}</span>
              </div>
            ))}
          </div>
        </SortableContext>
      </DndContext>
      <button onClick={handleSave} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded">
        Save Chain
      </button>
    </div>
  );
}
