/**
 * SignalChain components - Building blocks for audio signal chain visualization.
 *
 * Main components:
 * - SignalChainBuilder: Main builder interface with stage columns
 * - StageColumn: Column container for blocks at each stage
 * - ConnectionLine: Visual connector between stages
 *
 * Block components for each stage:
 * - BlockCard: Base component for all block types
 * - DITrackBlock: DI/Input (blue accent)
 * - AmpBlock: Amplifier/NAM models (amber accent)
 * - CabinetBlock: Cabinet/IR models (green accent)
 * - EffectBlock: Effects/pedals (purple accent)
 *
 * State management:
 * - useBuilderState: Hook for managing builder state
 * - types: Type definitions for blocks and state
 */

// Main builder components
export { SignalChainBuilder } from './SignalChainBuilder';
export { StageColumn } from './StageColumn';
export { SortableStageColumn } from './SortableStageColumn';
export { ConnectionLine } from './ConnectionLine';
export { OutputMatrix } from './OutputMatrix';
export { ToneSearchModal } from './ToneSearchModal';

// Sortable components (dnd-kit integration)
export { SortableBlock, SortableBlockHandle } from './SortableBlock';

// Block components
export { BlockCard, type BlockType } from './BlockCard';
export { DITrackBlock } from './DITrackBlock';
export { AmpBlock } from './AmpBlock';
export { CabinetBlock } from './CabinetBlock';
export {
  EffectBlock,
  type EffectType,
  type EffectParams,
  type EQParams,
  type DelayParams,
  type ReverbParams,
  type CompressionParams,
  type NoiseGateParams,
  type BoostParams,
} from './EffectBlock';

// State management
export { useBuilderState, type BuilderActions } from './useBuilderState';

// Types
export type {
  BlockStage,
  Block,
  DIBlock,
  AmpBlockData,
  CabBlockData,
  EffectBlockData,
  BuilderState,
  BuilderAction,
} from './types';
export { initialBuilderState, generateBlockId } from './types';
