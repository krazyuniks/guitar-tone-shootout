/**
 * SignalChainBuilder - Main component for building audio signal chains.
 *
 * Displays a horizontal layout of stage columns:
 * DI Tracks -> Amps -> Cabinets -> Effects -> Output
 *
 * On mobile, columns stack vertically.
 *
 * Features:
 * - State management with useBuilderState hook
 * - Drag-and-drop reordering within columns (via dnd-kit)
 * - Output matrix preview showing all combinations
 * - Tone 3000 search modal for adding amps/cabs
 */
import { useState, useCallback } from 'react';
import { Sparkles, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { QueryProvider } from '@/lib/query';
import { SortableStageColumn } from './SortableStageColumn';
import { SortableBlock } from './SortableBlock';
import { ConnectionLine } from './ConnectionLine';
import { OutputMatrix } from './OutputMatrix';
import { ToneSearchModal } from './ToneSearchModal';
import { DITrackBlock } from './DITrackBlock';
import { AmpBlock } from './AmpBlock';
import { CabinetBlock } from './CabinetBlock';
import { useBuilderState } from './useBuilderState';
import type { DIBlock, AmpBlockData, CabBlockData, EffectBlockData } from './types';
import { generateBlockId } from './types';
import type { Tone, Gear } from '@/lib/api';

interface SignalChainBuilderProps {
  /** Callback when the builder state changes */
  onChange?: (state: {
    diTracks: DIBlock[];
    amps: AmpBlockData[];
    cabs: CabBlockData[];
    effects: EffectBlockData[];
  }) => void;
  /** Maximum number of blocks per stage */
  maxBlocksPerStage?: number;
  /** Additional CSS classes */
  className?: string;
}

function SignalChainBuilderInner({
  onChange,
  maxBlocksPerStage = 4,
  className,
}: SignalChainBuilderProps) {
  const [state, actions] = useBuilderState();

  // Modal state - will be enhanced with actual modals in #45
  const [activeModal, setActiveModal] = useState<'di' | 'amp' | 'cab' | 'effect' | null>(null);

  // Notify parent of state changes
  const notifyChange = useCallback(() => {
    onChange?.(state);
  }, [state, onChange]);

  // Placeholder: Add DI Track (will be file upload modal)
  const handleAddDITrack = useCallback(() => {
    // For now, add a demo track - will be replaced with file upload
    const demoTrack: DIBlock = {
      id: generateBlockId(),
      stage: 'di',
      filename: `DI Track ${state.diTracks.length + 1}.wav`,
      duration: 30 + Math.random() * 60,
      sampleRate: 44100,
    };
    actions.addDITrack(demoTrack);
    notifyChange();
  }, [actions, notifyChange, state.diTracks.length]);

  // Placeholder: Add Amp (will open Tone 3000 search modal)
  const handleAddAmp = useCallback(() => {
    setActiveModal('amp');
  }, []);

  // Placeholder: Add Cabinet (will open Tone 3000 search modal)
  const handleAddCab = useCallback(() => {
    setActiveModal('cab');
  }, []);

  // Placeholder: Add Effect (will open Tone 3000 search modal)
  const handleAddEffect = useCallback(() => {
    setActiveModal('effect');
  }, []);

  // Remove handlers
  const handleRemoveDITrack = useCallback(
    (id: string) => {
      actions.removeDITrack(id);
      notifyChange();
    },
    [actions, notifyChange]
  );

  const handleRemoveAmp = useCallback(
    (id: string) => {
      actions.removeAmp(id);
      notifyChange();
    },
    [actions, notifyChange]
  );

  const handleRemoveCab = useCallback(
    (id: string) => {
      actions.removeCab(id);
      notifyChange();
    },
    [actions, notifyChange]
  );

  const handleRemoveEffect = useCallback(
    (id: string) => {
      actions.removeEffect(id);
      notifyChange();
    },
    [actions, notifyChange]
  );

  // Reorder handlers for drag-and-drop
  const handleReorderDITracks = useCallback(
    (items: DIBlock[]) => {
      actions.reorderDITracks(items);
      notifyChange();
    },
    [actions, notifyChange]
  );

  const handleReorderAmps = useCallback(
    (items: AmpBlockData[]) => {
      actions.reorderAmps(items);
      notifyChange();
    },
    [actions, notifyChange]
  );

  const handleReorderCabs = useCallback(
    (items: CabBlockData[]) => {
      actions.reorderCabs(items);
      notifyChange();
    },
    [actions, notifyChange]
  );

  const handleReorderEffects = useCallback(
    (items: EffectBlockData[]) => {
      actions.reorderEffects(items);
      notifyChange();
    },
    [actions, notifyChange]
  );

  // Handle adding a tone from search modal (for amp/cab/effect)
  const handleSelectTone = useCallback(
    (tone: Tone) => {
      if (activeModal === 'amp') {
        const block: AmpBlockData = {
          id: generateBlockId(),
          stage: 'amp',
          tone,
        };
        actions.addAmp(block);
      } else if (activeModal === 'cab') {
        const block: CabBlockData = {
          id: generateBlockId(),
          stage: 'cab',
          tone,
        };
        actions.addCab(block);
      } else if (activeModal === 'effect') {
        const block: EffectBlockData = {
          id: generateBlockId(),
          stage: 'effect',
          tone,
        };
        actions.addEffect(block);
      }
      setActiveModal(null);
      notifyChange();
    },
    [activeModal, actions, notifyChange]
  );

  // Get modal title and gear filter based on active modal
  const getModalConfig = (): { title: string; gearFilter?: Gear } => {
    switch (activeModal) {
      case 'amp':
        return { title: 'Add Amp Model', gearFilter: 'amp' };
      case 'cab':
        return { title: 'Add Cabinet/IR', gearFilter: 'ir' };
      case 'effect':
        return { title: 'Add Effect', gearFilter: 'pedal' };
      default:
        return { title: 'Select Tone' };
    }
  };

  const modalConfig = getModalConfig();

  return (
    <div className={cn('w-full', className)}>
      {/* Main builder layout */}
      <div
        className={cn(
          'flex gap-4',
          // Horizontal on desktop, vertical on mobile
          'flex-col lg:flex-row lg:items-start',
          'overflow-x-auto pb-4'
        )}
      >
        {/* DI Tracks Column - with drag-and-drop */}
        <SortableStageColumn
          stage="di"
          title="DI Tracks"
          items={state.diTracks}
          onReorder={handleReorderDITracks}
          onAddClick={handleAddDITrack}
          addDisabled={state.diTracks.length >= maxBlocksPerStage}
          renderItem={(track) => (
            <SortableBlock key={track.id} id={track.id}>
              <div className="relative">
                <DITrackBlock
                  filename={track.filename}
                  duration={track.duration}
                  sampleRate={track.sampleRate}
                  showDragHandle
                  className="pr-8"
                />
                <button
                  type="button"
                  onClick={() => handleRemoveDITrack(track.id)}
                  className="absolute right-2 top-2 rounded-full p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
                  aria-label={`Remove ${track.filename}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </SortableBlock>
          )}
        />

        <ConnectionLine />

        {/* Amps Column - with drag-and-drop */}
        <SortableStageColumn
          stage="amp"
          title="Amps"
          items={state.amps}
          onReorder={handleReorderAmps}
          onAddClick={handleAddAmp}
          addDisabled={state.amps.length >= maxBlocksPerStage}
          renderItem={(amp) => (
            <SortableBlock key={amp.id} id={amp.id}>
              <AmpBlock
                tone={amp.tone}
                onRemove={() => handleRemoveAmp(amp.id)}
              />
            </SortableBlock>
          )}
        />

        <ConnectionLine />

        {/* Cabinets Column - with drag-and-drop */}
        <SortableStageColumn
          stage="cab"
          title="Cabinets"
          items={state.cabs}
          onReorder={handleReorderCabs}
          onAddClick={handleAddCab}
          addDisabled={state.cabs.length >= maxBlocksPerStage}
          renderItem={(cab) => (
            <SortableBlock key={cab.id} id={cab.id}>
              <CabinetBlock
                tone={cab.tone}
                onRemove={() => handleRemoveCab(cab.id)}
              />
            </SortableBlock>
          )}
        />

        <ConnectionLine />

        {/* Effects Column - with drag-and-drop */}
        <SortableStageColumn
          stage="effect"
          title="Effects"
          items={state.effects}
          onReorder={handleReorderEffects}
          onAddClick={handleAddEffect}
          addDisabled={state.effects.length >= maxBlocksPerStage}
          renderItem={(effect) => (
            <SortableBlock key={effect.id} id={effect.id}>
              <EffectBlock
                tone={effect.tone}
                onRemove={() => handleRemoveEffect(effect.id)}
              />
            </SortableBlock>
          )}
        />
      </div>

      {/* Output Matrix Preview */}
      <OutputMatrix
        diTracks={state.diTracks}
        amps={state.amps}
        cabs={state.cabs}
        className="mt-6"
      />

      {/* Tone 3000 Search Modal */}
      <ToneSearchModal
        isOpen={activeModal === 'amp' || activeModal === 'cab' || activeModal === 'effect'}
        onClose={() => setActiveModal(null)}
        onSelect={handleSelectTone}
        title={modalConfig.title}
        gearFilter={modalConfig.gearFilter}
      />
    </div>
  );
}

/**
 * Effect Block component - placeholder until we have a dedicated component
 */
function EffectBlock({
  tone,
  onRemove,
}: {
  tone: Tone;
  onRemove?: () => void;
}) {
  return (
    <div className="relative rounded-lg border border-purple-500/30 bg-card p-4 hover:border-purple-500/50">
      {onRemove && (
        <button
          onClick={onRemove}
          className="absolute right-2 top-2 rounded-full p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
          aria-label={`Remove ${tone.title}`}
        >
          <X className="h-4 w-4" />
        </button>
      )}
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-purple-500/20">
          <Sparkles className="h-4 w-4 text-purple-500" />
        </div>
        <span className="text-xs font-semibold uppercase tracking-wider text-purple-500">
          Effect
        </span>
      </div>
      <h4 className="truncate pr-6 font-medium text-foreground">{tone.title}</h4>
      {tone.makes.length > 0 && (
        <p className="text-sm text-muted-foreground">{tone.makes[0].name}</p>
      )}
    </div>
  );
}

/**
 * SignalChainBuilder wrapped with QueryProvider for data fetching.
 */
export function SignalChainBuilder(props: SignalChainBuilderProps) {
  return (
    <QueryProvider>
      <SignalChainBuilderInner {...props} />
    </QueryProvider>
  );
}
