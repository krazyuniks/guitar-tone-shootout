/**
 * Custom SVG icons for signal chain block types.
 *
 * Each icon follows the block type color scheme defined in global.css:
 * - DI Track: Blue #3b82f6 (--color-block-di)
 * - Amp Model: Amber #f59e0b (--color-block-amp)
 * - Cabinet/IR: Green #22c55e (--color-block-cab)
 * - Effect: Purple #a855f7 (--color-block-effect)
 *
 * Icons are designed to work with currentColor for flexible theming.
 */

export { DITrackIcon } from "./DITrackIcon";
export { AmpModelIcon } from "./AmpModelIcon";
export { CabinetIcon } from "./CabinetIcon";
export { EffectIcon } from "./EffectIcon";

// Re-export block type for convenience
export type { BlockType } from "@/components/SignalChain/BlockCard";
