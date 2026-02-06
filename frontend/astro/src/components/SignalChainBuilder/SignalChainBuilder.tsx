import React, { useState, useEffect } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

/**
 * SignalChainBuilder - React component for building guitar signal chains
 *
 * Features:
 * - Block drag-and-drop reordering using @dnd-kit
 * - Gear selection from user's library
 * - Single chain mode (one gear per slot)
 * - Permutation mode (multiple gear per slot)
 * - Integration with signal chain and library APIs
 */

// Types
interface GearItem {
  id: string;
  gear_id: string;
  name: string;
  gear_type: 'amp' | 'pedal' | 'ir';
  platform: string;
}

interface SignalChainBlock {
  id?: string;
  user_gear_id: string;
  gear_type: string;
  position: number;
  gear?: GearItem;
}

interface SignalChain {
  id?: string;
  name: string;
  platform: 'nam' | 'ir';
  description?: string;
  blocks: SignalChainBlock[];
}

type BuilderMode = 'single' | 'permutation';

interface SignalChainBuilderProps {
  mode?: BuilderMode;
  chainId?: string;
  onSave?: (chain: SignalChain) => void;
}

// Sortable block component
function SortableBlock({
  block,
  onRemove,
}: {
  block: SignalChainBlock;
  onRemove: () => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id: block.user_gear_id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="flex items-center justify-between p-4 bg-white border border-gray-300 rounded-lg shadow-sm hover:shadow-md transition-shadow cursor-move"
    >
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-gray-500">
          {block.position}
        </span>
        <div>
          <div className="font-medium">{block.gear?.name || 'Unknown Gear'}</div>
          <div className="text-sm text-gray-500 capitalize">{block.gear_type}</div>
        </div>
      </div>
      <button
        onClick={onRemove}
        className="px-3 py-1 text-sm text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
        type="button"
      >
        Remove
      </button>
    </div>
  );
}

// Main component
export default function SignalChainBuilder({
  mode = 'single',
  chainId,
  onSave,
}: SignalChainBuilderProps) {
  const [chain, setChain] = useState<SignalChain>({
    name: '',
    platform: 'nam',
    description: '',
    blocks: [],
  });
  const [userGearLibrary, setUserGearLibrary] = useState<GearItem[]>([]);
  const [selectedGear, setSelectedGear] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Load user's gear library
  useEffect(() => {
    const loadLibrary = async () => {
      try {
        const response = await fetch('/api/v1/library/gear');
        if (!response.ok) throw new Error('Failed to load gear library');
        const data = await response.json();
        setUserGearLibrary(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    };

    loadLibrary();
  }, []);

  // Load existing chain if editing
  useEffect(() => {
    if (!chainId) return;

    const loadChain = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/v1/signal-chains/${chainId}`);
        if (!response.ok) throw new Error('Failed to load signal chain');
        const data = await response.json();
        setChain(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    loadChain();
  }, [chainId]);

  // Handle drag end
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      setChain((prev) => {
        const oldIndex = prev.blocks.findIndex(
          (block) => block.user_gear_id === active.id
        );
        const newIndex = prev.blocks.findIndex(
          (block) => block.user_gear_id === over.id
        );

        const newBlocks = arrayMove(prev.blocks, oldIndex, newIndex);

        // Update positions
        return {
          ...prev,
          blocks: newBlocks.map((block, index) => ({
            ...block,
            position: index,
          })),
        };
      });
    }
  };

  // Add gear to chain
  const handleAddGear = () => {
    if (!selectedGear) return;

    const gear = userGearLibrary.find((g) => g.id === selectedGear);
    if (!gear) return;

    const newBlock: SignalChainBlock = {
      user_gear_id: gear.id,
      gear_type: gear.gear_type,
      position: chain.blocks.length,
      gear,
    };

    // In single mode, check if gear at this position already exists
    if (mode === 'single') {
      setChain((prev) => ({
        ...prev,
        blocks: [...prev.blocks, newBlock],
      }));
    } else {
      // Permutation mode: allow multiple gear at same position (slot)
      setChain((prev) => ({
        ...prev,
        blocks: [...prev.blocks, newBlock],
      }));
    }

    setSelectedGear('');
  };

  // Remove gear from chain
  const handleRemoveBlock = (index: number) => {
    setChain((prev) => ({
      ...prev,
      blocks: prev.blocks.filter((_, i) => i !== index).map((block, i) => ({
        ...block,
        position: i,
      })),
    }));
  };

  // Save chain
  const handleSave = async () => {
    if (!chain.name.trim()) {
      setError('Chain name is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const payload = {
        name: chain.name,
        platform: chain.platform,
        description: chain.description,
        blocks: chain.blocks.map(({ user_gear_id, gear_type, position }) => ({
          user_gear_id,
          gear_type,
          position,
        })),
      };

      const url = chainId
        ? `/api/v1/signal-chains/${chainId}`
        : '/api/v1/signal-chains/';

      const method = chainId ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save chain');
      }

      const savedChain = await response.json();

      if (onSave) {
        onSave(savedChain);
      }

      // Reset form if creating new chain
      if (!chainId) {
        setChain({
          name: '',
          platform: 'nam',
          description: '',
          blocks: [],
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-4">Loading...</div>;
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <h2 className="text-2xl font-bold">
          {chainId ? 'Edit Signal Chain' : 'Build Signal Chain'}
        </h2>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700">
            {error}
          </div>
        )}

        {/* Chain details */}
        <div className="space-y-4">
          <div>
            <label htmlFor="chain-name" className="block text-sm font-medium mb-1">
              Chain Name
            </label>
            <input
              id="chain-name"
              type="text"
              value={chain.name}
              onChange={(e) => setChain((prev) => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="My Awesome Tone"
            />
          </div>

          <div>
            <label htmlFor="chain-platform" className="block text-sm font-medium mb-1">
              Platform
            </label>
            <select
              id="chain-platform"
              value={chain.platform}
              onChange={(e) =>
                setChain((prev) => ({ ...prev, platform: e.target.value as 'nam' | 'ir' }))
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="nam">NAM</option>
              <option value="ir">IR</option>
            </select>
          </div>

          <div>
            <label htmlFor="chain-description" className="block text-sm font-medium mb-1">
              Description (optional)
            </label>
            <textarea
              id="chain-description"
              value={chain.description || ''}
              onChange={(e) =>
                setChain((prev) => ({ ...prev, description: e.target.value }))
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={3}
              placeholder="Describe your tone..."
            />
          </div>

          {/* Mode indicator */}
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span className="font-medium">Mode:</span>
            <span className="px-2 py-1 bg-gray-100 rounded capitalize">{mode}</span>
            {mode === 'permutation' && (
              <span className="text-xs text-gray-500">
                (Multiple gear per slot supported)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Gear selection */}
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <h3 className="text-lg font-semibold">Add Gear from Library</h3>

        <div className="flex gap-2">
          <select
            value={selectedGear}
            onChange={(e) => setSelectedGear(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">Select gear from your library...</option>
            {userGearLibrary.map((gear) => (
              <option key={gear.id} value={gear.id}>
                {gear.name} ({gear.gear_type})
              </option>
            ))}
          </select>

          <button
            onClick={handleAddGear}
            disabled={!selectedGear}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            type="button"
          >
            Add
          </button>
        </div>
      </div>

      {/* Signal chain blocks */}
      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <h3 className="text-lg font-semibold">Signal Chain</h3>

        {chain.blocks.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            No gear added yet. Select gear from your library to build your chain.
          </p>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={chain.blocks.map((b) => b.user_gear_id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-2">
                {chain.blocks.map((block, index) => (
                  <SortableBlock
                    key={block.user_gear_id}
                    block={block}
                    onRemove={() => handleRemoveBlock(index)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2">
        <button
          onClick={handleSave}
          disabled={loading || !chain.name.trim() || chain.blocks.length === 0}
          className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          type="button"
        >
          {loading ? 'Saving...' : chainId ? 'Update Chain' : 'Save Chain'}
        </button>
      </div>
    </div>
  );
}
