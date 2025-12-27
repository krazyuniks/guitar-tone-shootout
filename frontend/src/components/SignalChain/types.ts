/**
 * Type definitions for Signal Chain Builder components.
 *
 * These types define the data structures for blocks at each stage
 * of the signal chain: DI, Amp, Cabinet, and Effect.
 */
import type { Tone } from '@/lib/api';

/** Block stages in the signal chain */
export type BlockStage = 'di' | 'amp' | 'cab' | 'effect';

/** Base interface for all blocks */
interface BaseBlock {
  /** Unique identifier for the block */
  id: string;
  /** Stage this block belongs to */
  stage: BlockStage;
}

/** DI Track block - represents an uploaded audio file */
export interface DIBlock extends BaseBlock {
  stage: 'di';
  /** Display name for the track */
  filename: string;
  /** Duration in seconds */
  duration: number;
  /** Sample rate in Hz */
  sampleRate: number;
  /** Path to the uploaded file on the server */
  uploadPath?: string;
}

/** Amp block - represents a Tone 3000 amp model */
export interface AmpBlockData extends BaseBlock {
  stage: 'amp';
  /** Tone 3000 tone data */
  tone: Tone;
}

/** Cabinet block - represents a Tone 3000 cabinet/IR */
export interface CabBlockData extends BaseBlock {
  stage: 'cab';
  /** Tone 3000 tone data */
  tone: Tone;
}

/** Effect block - represents a Tone 3000 effect/pedal */
export interface EffectBlockData extends BaseBlock {
  stage: 'effect';
  /** Tone 3000 tone data */
  tone: Tone;
}

/** Union type for all block types */
export type Block = DIBlock | AmpBlockData | CabBlockData | EffectBlockData;

/** State for the entire signal chain builder */
export interface BuilderState {
  diTracks: DIBlock[];
  amps: AmpBlockData[];
  cabs: CabBlockData[];
  effects: EffectBlockData[];
}

/** Actions for the builder reducer */
export type BuilderAction =
  | { type: 'ADD_DI_TRACK'; payload: DIBlock }
  | { type: 'REMOVE_DI_TRACK'; payload: string }
  | { type: 'REORDER_DI_TRACKS'; payload: DIBlock[] }
  | { type: 'ADD_AMP'; payload: AmpBlockData }
  | { type: 'REMOVE_AMP'; payload: string }
  | { type: 'REORDER_AMPS'; payload: AmpBlockData[] }
  | { type: 'ADD_CAB'; payload: CabBlockData }
  | { type: 'REMOVE_CAB'; payload: string }
  | { type: 'REORDER_CABS'; payload: CabBlockData[] }
  | { type: 'ADD_EFFECT'; payload: EffectBlockData }
  | { type: 'REMOVE_EFFECT'; payload: string }
  | { type: 'REORDER_EFFECTS'; payload: EffectBlockData[] }
  | { type: 'RESET' };

/** Initial empty state for the builder */
export const initialBuilderState: BuilderState = {
  diTracks: [],
  amps: [],
  cabs: [],
  effects: [],
};

/** Generate a unique ID for blocks */
export function generateBlockId(): string {
  return `block-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
}
