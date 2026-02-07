/**
 * Hook for fetching signal chain builder guidance from the domain.
 *
 * Converts builder state to API format and queries the guidance endpoint
 * to get valid next gear types and user-friendly guidance messages.
 */
import { useQuery } from '@tanstack/react-query';
import {
  signalChainApi,
  type SignalChainGuidanceBlock,
  type SignalChainGuidanceResponse,
  type SignalChainGearType,
  type Gear,
} from '@/lib/api';
import type { BuilderState } from './types';

/**
 * Maps frontend Gear type to backend GearType for pre-amp pedals.
 * Frontend uses "full-rig" (with hyphen), backend uses "full_rig" (with underscore).
 */
function mapGearToApiGearType(gear: Gear): SignalChainGearType {
  switch (gear) {
    case 'full-rig':
      return 'full_rig';
    case 'amp':
      return 'amp';
    case 'pedal':
      return 'pedal';
    case 'ir':
      return 'ir';
    case 'outboard':
      // Outboard gear is treated as pedal for signal chain purposes
      return 'pedal';
    default:
      return 'pedal';
  }
}

/**
 * Converts builder state to API guidance request blocks.
 *
 * Signal chain grammar: [PrePedals*] -> AmpBlock -> [IRBlock?] -> [PostEffects*]
 *
 * The order in the builder is:
 * - effects (pre-amp pedals) - position at start
 * - amps - position after pedals
 * - cabs (IR) - position after amps
 * - postEffects (post-amp effects) - position at end
 */
function builderStateToGuidanceBlocks(state: BuilderState): SignalChainGuidanceBlock[] {
  const blocks: SignalChainGuidanceBlock[] = [];

  // Effects/pedals come first in the signal chain (pre-amp)
  for (const effect of state.effects) {
    blocks.push({
      gear_type: mapGearToApiGearType(effect.tone.gear),
    });
  }

  // Amps come next
  for (const amp of state.amps) {
    blocks.push({
      gear_type: mapGearToApiGearType(amp.tone.gear),
    });
  }

  // Cabinets (IRs) come after amps
  for (const _cab of state.cabs) {
    blocks.push({
      gear_type: 'ir', // Cabs are always IR type
    });
  }

  // Post-effects come last (delay, reverb, etc.)
  for (const _postEffect of state.postEffects) {
    blocks.push({
      gear_type: 'post_effect',
    });
  }

  return blocks;
}

/**
 * Default guidance when no API call is needed (empty state).
 */
const defaultGuidance: SignalChainGuidanceResponse = {
  next_valid_gear_types: ['pedal', 'amp', 'full_rig'],
  guidance_message: 'Choose the first piece of gear in your signal chain.',
  is_complete: false,
};

export interface UseSignalChainGuidanceResult {
  /** Whether the guidance is being fetched */
  isLoading: boolean;
  /** Any error that occurred */
  error: Error | null;
  /** The guidance response from the API */
  guidance: SignalChainGuidanceResponse;
  /** Helper: Can add a pedal (pre-amp)? */
  canAddPedal: boolean;
  /** Helper: Can add an amp? */
  canAddAmp: boolean;
  /** Helper: Can add a full-rig? */
  canAddFullRig: boolean;
  /** Helper: Can add an IR/cabinet? */
  canAddIR: boolean;
  /** Helper: Can add a post-effect (delay, reverb, etc.)? */
  canAddPostEffect: boolean;
}

/**
 * Hook for fetching signal chain guidance based on current builder state.
 *
 * @param state - Current builder state
 * @returns Guidance including valid next gear types and messages
 */
export function useSignalChainGuidance(state: BuilderState): UseSignalChainGuidanceResult {
  const blocks = builderStateToGuidanceBlocks(state);

  const { data, isLoading, error } = useQuery({
    queryKey: ['signalChainGuidance', blocks],
    queryFn: () => signalChainApi.guidance({ blocks }),
    // Use stale-while-revalidate for snappy UX
    staleTime: 1000,
    // Keep previous data while loading new
    placeholderData: (previousData) => previousData,
  });

  const guidance = data ?? defaultGuidance;

  return {
    isLoading,
    error: error as Error | null,
    guidance,
    canAddPedal: guidance.next_valid_gear_types.includes('pedal'),
    canAddAmp: guidance.next_valid_gear_types.includes('amp'),
    canAddFullRig: guidance.next_valid_gear_types.includes('full_rig'),
    canAddIR: guidance.next_valid_gear_types.includes('ir'),
    canAddPostEffect: guidance.next_valid_gear_types.includes('post_effect'),
  };
}
