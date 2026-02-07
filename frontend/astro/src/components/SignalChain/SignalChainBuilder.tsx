/**
 * SignalChainBuilder - Main component for building audio signal chains.
 *
 * Displays a horizontal layout of stage columns:
 * DI Tracks -> Pedals -> Amps -> Cabinets -> Post-Effects
 *
 * Signal Chain Grammar:
 *   [DI Tracks] -> [PrePedals*] -> AmpBlock -> [IRBlock?] -> [PostEffects*]
 *
 * On mobile, columns stack vertically.
 *
 * Features:
 * - State management with useBuilderState hook
 * - Drag-and-drop reordering within columns (via dnd-kit)
 * - Output matrix preview showing all combinations
 * - Tone 3000 search modal for adding amps/cabs
 * - Save signal chain to library
 * - Visual states (active, inactive, complete) for UX guidance
 */
import { useState, useCallback, useMemo } from 'react';
import { Sparkles, Clock, X, Save, Info, CheckCircle2, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { QueryProvider } from '@/lib/query';
import { SortableStageColumn } from './SortableStageColumn';
import { SortableBlock } from './SortableBlock';
import { ConnectionLine } from './ConnectionLine';
import { OutputMatrix } from './OutputMatrix';
import { ToneSearchModal } from './ToneSearchModal';
import { DITrackSelectModal } from './DITrackSelectModal';
import { SaveChainDialog } from './SaveChainDialog';
import { DITrackBlock } from './DITrackBlock';
import type { DITrackListItem } from '@/lib/api';
import { AmpBlock } from './AmpBlock';
import { CabinetBlock } from './CabinetBlock';
import { useBuilderState } from './useBuilderState';
import { useSignalChainGuidance, type UseSignalChainGuidanceResult } from './useSignalChainGuidance';
import type { ColumnState } from './StageColumn';
import { Button } from '@/components/ui/button';
import type { DIBlock, AmpBlockData, CabBlockData, EffectBlockData, PostEffectBlockData, BuilderState } from './types';
import { generateBlockId } from './types';
import type { Tone, Gear } from '@/lib/api';

/**
 * Determines the visual state for each column based on chain state and guidance.
 *
 * Logic:
 * - DI column is always "complete" (optional input)
 * - A column is "complete" if it has items and those items satisfy the chain requirements
 * - A column is "active" if user can currently add items to it (per guidance)
 * - A column is "inactive" if it's not available yet in the signal flow
 */
function getColumnStates(
  state: BuilderState,
  guidance: UseSignalChainGuidanceResult
): {
  di: ColumnState;
  pedals: ColumnState;
  amps: ColumnState;
  cabs: ColumnState;
  postEffects: ColumnState;
} {
  const { canAddPedal, canAddAmp, canAddFullRig, canAddIR, canAddPostEffect } = guidance;
  const isComplete = guidance.guidance.is_complete;

  // Check if any amp is a full-rig (has built-in cab)
  const hasFullRig = state.amps.some(amp => amp.tone.gear === 'full-rig');
  const hasAmp = state.amps.length > 0;
  const hasCab = state.cabs.length > 0;
  const hasEffects = state.effects.length > 0;
  const hasPostEffects = state.postEffects.length > 0;

  // DI is always complete (optional starting point)
  const diState: ColumnState = 'complete';

  // Pedals: active if can add, complete if has effects and moved past
  let pedalsState: ColumnState;
  if (canAddPedal) {
    pedalsState = 'active';
  } else if (hasEffects) {
    pedalsState = 'complete';
  } else {
    pedalsState = hasAmp ? 'complete' : 'inactive';
  }

  // Amps: active if can add amp/full-rig, complete if has amp
  let ampsState: ColumnState;
  if (canAddAmp || canAddFullRig) {
    ampsState = 'active';
  } else if (hasAmp) {
    ampsState = 'complete';
  } else {
    ampsState = 'inactive';
  }

  // Cabs/IR: active if can add IR, complete if has cab or full-rig (no IR needed)
  let cabsState: ColumnState;
  if (canAddIR) {
    cabsState = 'active';
  } else if (hasCab || hasFullRig) {
    cabsState = 'complete';
  } else if (hasAmp) {
    // Amp head requires IR, but can't add yet - shouldn't happen, but handle it
    cabsState = 'active';
  } else {
    cabsState = 'inactive';
  }

  // Post-effects: active if can add, complete if chain is complete with post-effects
  let postEffectsState: ColumnState;
  if (canAddPostEffect) {
    postEffectsState = 'active';
  } else if (hasPostEffects) {
    postEffectsState = 'complete';
  } else if (isComplete) {
    // Chain complete, post-effects available but none added
    postEffectsState = 'complete';
  } else {
    postEffectsState = 'inactive';
  }

  return {
    di: diState,
    pedals: pedalsState,
    amps: ampsState,
    cabs: cabsState,
    postEffects: postEffectsState,
  };
}

/**
 * Generates contextual empty state messages based on chain state.
 */
function getEmptyMessages(
  state: BuilderState,
  guidance: UseSignalChainGuidanceResult
): {
  pedals: string;
  amps: string;
  cabs: string;
  postEffects: string;
} {
  const hasAmp = state.amps.length > 0;
  const hasFullRig = state.amps.some(amp => amp.tone.gear === 'full-rig');
  const hasCab = state.cabs.length > 0;
  const isComplete = guidance.guidance.is_complete;

  return {
    pedals: hasAmp
      ? 'Pedals placed before amp in chain'
      : 'Add pedals (optional) or skip to Amps',
    amps: 'Add an amp to shape your tone',
    cabs: hasFullRig
      ? 'Full-rig includes cabinet - no IR needed'
      : hasAmp
        ? 'Add a cabinet IR to complete your chain'
        : 'Add an amp first to unlock cabinets',
    postEffects: isComplete
      ? 'Chain complete! Add post-effects (optional)'
      : hasCab || hasFullRig
        ? 'Add delay, reverb, and other post-effects'
        : 'Complete your amp/cab chain first',
  };
}

interface SignalChainBuilderProps {
  /** Callback when the builder state changes */
  onChange?: (state: {
    diTracks: DIBlock[];
    amps: AmpBlockData[];
    cabs: CabBlockData[];
    effects: EffectBlockData[];
    postEffects: PostEffectBlockData[];
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

  // Signal chain guidance from domain
  const guidanceResult = useSignalChainGuidance(state);
  const { guidance, canAddPedal, canAddAmp, canAddFullRig, canAddIR, canAddPostEffect } = guidanceResult;

  // Compute visual states for columns
  const columnStates = useMemo(
    () => getColumnStates(state, guidanceResult),
    [state, guidanceResult]
  );

  // Compute contextual empty messages
  const emptyMessages = useMemo(
    () => getEmptyMessages(state, guidanceResult),
    [state, guidanceResult]
  );

  // Modal state
  const [activeModal, setActiveModal] = useState<'amp' | 'cab' | 'effect' | 'postEffect' | null>(null);
  const [showDITrackModal, setShowDITrackModal] = useState(false);

  // Save dialog state
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [lastSavedChainId, setLastSavedChainId] = useState<string | null>(null);

  // Notify parent of state changes
  const notifyChange = useCallback(() => {
    onChange?.(state);
  }, [state, onChange]);

  // Open DI track selection modal
  const handleAddDITrack = useCallback(() => {
    setShowDITrackModal(true);
  }, []);

  // Handle DI track selection from modal
  const handleSelectDITrack = useCallback(
    (track: DITrackListItem) => {
      const diBlock: DIBlock = {
        id: generateBlockId(),
        stage: 'di',
        filename: track.title,
        duration: track.duration_seconds,
        sampleRate: track.sample_rate,
        // Store the track ID for later reference (e.g., when saving the chain)
        uploadPath: track.id,
      };
      actions.addDITrack(diBlock);
      notifyChange();
    },
    [actions, notifyChange]
  );

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

  // Placeholder: Add Post-Effect (will open Tone 3000 search modal)
  const handleAddPostEffect = useCallback(() => {
    setActiveModal('postEffect');
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

  const handleRemovePostEffect = useCallback(
    (id: string) => {
      actions.removePostEffect(id);
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

  const handleReorderPostEffects = useCallback(
    (items: PostEffectBlockData[]) => {
      actions.reorderPostEffects(items);
      notifyChange();
    },
    [actions, notifyChange]
  );

  // Handle adding a tone from search modal (for amp/cab/effect/postEffect)
  // user_gear_id is provided when selecting from library tab (not from search)
  const handleSelectTone = useCallback(
    (tone: Tone, user_gear_id?: string) => {
      if (activeModal === 'amp') {
        const block: AmpBlockData = {
          id: generateBlockId(),
          stage: 'amp',
          tone,
          user_gear_id,
        };
        actions.addAmp(block);
      } else if (activeModal === 'cab') {
        const block: CabBlockData = {
          id: generateBlockId(),
          stage: 'cab',
          tone,
          user_gear_id,
        };
        actions.addCab(block);
      } else if (activeModal === 'effect') {
        const block: EffectBlockData = {
          id: generateBlockId(),
          stage: 'effect',
          tone,
          user_gear_id,
        };
        actions.addEffect(block);
      } else if (activeModal === 'postEffect') {
        const block: PostEffectBlockData = {
          id: generateBlockId(),
          stage: 'postEffect',
          tone,
          user_gear_id,
        };
        actions.addPostEffect(block);
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
        return { title: 'Add Pre-Amp Pedal', gearFilter: 'pedal' };
      case 'postEffect':
        return { title: 'Add Post-Amp Effect', gearFilter: 'pedal' };
      default:
        return { title: 'Select Tone' };
    }
  };

  const modalConfig = getModalConfig();

  // Check if there's anything to save
  const hasBlocks = state.amps.length > 0 || state.cabs.length > 0 || state.effects.length > 0 || state.postEffects.length > 0;

  // Handle save success
  const handleSaveSuccess = useCallback((chainId: string) => {
    setLastSavedChainId(chainId);
    actions.reset();
    notifyChange();
  }, [actions, notifyChange]);

  return (
    <div className={cn('w-full', className)}>
      {/* Guidance Banner */}
      <div
        className={cn(
          'mb-4 flex items-center gap-3 rounded-lg border p-4',
          guidance.is_complete
            ? 'border-green-500/30 bg-green-500/10'
            : 'border-[var(--color-accent-primary)]/30 bg-[var(--color-accent-primary)]/10'
        )}
      >
        {guidance.is_complete ? (
          <CheckCircle2 className="h-5 w-5 shrink-0 text-green-500" />
        ) : (
          <Info className="h-5 w-5 shrink-0 text-[var(--color-accent-primary)]" />
        )}
        <p className="text-sm text-foreground">{guidance.guidance_message}</p>
      </div>

      {/* Header with save button */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          {lastSavedChainId && (
            <a
              href="/library/chains"
              className="text-sm text-[var(--color-accent-primary)] hover:underline"
            >
              Chain saved! View in library
            </a>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowSaveDialog(true)}
          disabled={!hasBlocks || !guidance.is_complete}
          title={
            !hasBlocks
              ? 'Add blocks to save'
              : !guidance.is_complete
                ? 'Complete your signal chain first'
                : 'Save signal chain'
          }
        >
          <Save className="mr-2 h-4 w-4" />
          Save Chain
        </Button>
      </div>

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
          columnState={columnStates.di}
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

        {/* Pedals Column - BEFORE amp in signal chain: [Pedals*] -> Amp -> [IR?] */}
        <SortableStageColumn
          stage="effect"
          title="Pedals"
          items={state.effects}
          onReorder={handleReorderEffects}
          onAddClick={handleAddEffect}
          addDisabled={state.effects.length >= maxBlocksPerStage || !canAddPedal}
          columnState={columnStates.pedals}
          emptyMessage={emptyMessages.pedals}
          renderItem={(effect) => (
            <SortableBlock key={effect.id} id={effect.id}>
              <EffectBlock
                tone={effect.tone}
                onRemove={() => handleRemoveEffect(effect.id)}
              />
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
          addDisabled={state.amps.length >= maxBlocksPerStage || (!canAddAmp && !canAddFullRig)}
          columnState={columnStates.amps}
          emptyMessage={emptyMessages.amps}
          renderItem={(amp) => (
            <SortableBlock key={amp.id} id={amp.id}>
              <AmpBlockWithIndicator
                tone={amp.tone}
                onRemove={() => handleRemoveAmp(amp.id)}
                isFullRig={amp.tone.gear === 'full-rig'}
              />
            </SortableBlock>
          )}
        />

        <ConnectionLine />

        {/* Cabinets Column - IR required after head amp, forbidden after full-rig */}
        <SortableStageColumn
          stage="cab"
          title="Cabinets (IR)"
          items={state.cabs}
          onReorder={handleReorderCabs}
          onAddClick={handleAddCab}
          addDisabled={state.cabs.length >= maxBlocksPerStage || !canAddIR}
          columnState={columnStates.cabs}
          emptyMessage={emptyMessages.cabs}
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

        {/* Post-Effects Column - After cab/IR: delay, reverb, etc. */}
        <SortableStageColumn
          stage="postEffect"
          title="Post-Effects"
          items={state.postEffects}
          onReorder={handleReorderPostEffects}
          onAddClick={handleAddPostEffect}
          addDisabled={state.postEffects.length >= maxBlocksPerStage || !canAddPostEffect}
          columnState={columnStates.postEffects}
          emptyMessage={emptyMessages.postEffects}
          renderItem={(postEffect) => (
            <SortableBlock key={postEffect.id} id={postEffect.id}>
              <PostEffectBlock
                tone={postEffect.tone}
                onRemove={() => handleRemovePostEffect(postEffect.id)}
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

      {/* DI Track Selection Modal */}
      <DITrackSelectModal
        isOpen={showDITrackModal}
        onClose={() => setShowDITrackModal(false)}
        onSelect={handleSelectDITrack}
        title="Select DI Track"
      />

      {/* Tone 3000 Search Modal */}
      <ToneSearchModal
        isOpen={activeModal === 'amp' || activeModal === 'cab' || activeModal === 'effect' || activeModal === 'postEffect'}
        onClose={() => setActiveModal(null)}
        onSelect={handleSelectTone}
        title={modalConfig.title}
        gearFilter={modalConfig.gearFilter}
      />

      {/* Save Chain Dialog */}
      <SaveChainDialog
        isOpen={showSaveDialog}
        onClose={() => setShowSaveDialog(false)}
        builderState={state}
        onSuccess={handleSaveSuccess}
      />
    </div>
  );
}

/**
 * AmpBlock with full-rig indicator - wrapper that adds visual indicator for full-rigs
 */
function AmpBlockWithIndicator({
  tone,
  onRemove,
  isFullRig,
}: {
  tone: Tone;
  onRemove?: () => void;
  isFullRig: boolean;
}) {
  return (
    <div className="relative">
      <AmpBlock tone={tone} onRemove={onRemove} />
      {/* Full-rig indicator badge */}
      {isFullRig && (
        <div
          className="absolute -right-2 -top-2 flex items-center gap-1 rounded-full border border-green-500/50 bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-400"
          title="Full-rig: Includes cabinet - no IR needed"
        >
          <Zap className="h-3 w-3" />
          <span>Full Rig</span>
        </div>
      )}
    </div>
  );
}

/**
 * Effect Block component - for pre-amp pedals (overdrive, fuzz, etc.)
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
          Pedal
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
 * Post-Effect Block component - for post-amp effects (delay, reverb, etc.)
 */
function PostEffectBlock({
  tone,
  onRemove,
}: {
  tone: Tone;
  onRemove?: () => void;
}) {
  return (
    <div className="relative rounded-lg border border-cyan-500/30 bg-card p-4 hover:border-cyan-500/50">
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
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-cyan-500/20">
          <Clock className="h-4 w-4 text-cyan-500" />
        </div>
        <span className="text-xs font-semibold uppercase tracking-wider text-cyan-500">
          Post-FX
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
