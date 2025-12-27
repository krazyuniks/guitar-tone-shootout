/**
 * SignalChain components - Building blocks for audio signal chain visualization.
 *
 * Each block represents a stage in the guitar signal processing chain:
 * - BlockCard: Base component for all block types
 * - DITrackBlock: DI/Input (blue accent)
 * - AmpBlock: Amplifier/NAM models (amber accent)
 * - CabinetBlock: Cabinet/IR models (green accent)
 * - EffectBlock: Effects/pedals (purple accent)
 */
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
