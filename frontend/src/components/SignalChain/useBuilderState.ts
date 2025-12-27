/**
 * Builder state management hook.
 *
 * Uses useReducer for predictable state updates across all signal chain stages.
 */
import { useReducer, useCallback } from 'react';
import type {
  BuilderState,
  BuilderAction,
  DIBlock,
  AmpBlockData,
  CabBlockData,
  EffectBlockData,
} from './types';
import { initialBuilderState } from './types';

function builderReducer(state: BuilderState, action: BuilderAction): BuilderState {
  switch (action.type) {
    // DI Track actions
    case 'ADD_DI_TRACK':
      return { ...state, diTracks: [...state.diTracks, action.payload] };
    case 'REMOVE_DI_TRACK':
      return {
        ...state,
        diTracks: state.diTracks.filter((t) => t.id !== action.payload),
      };
    case 'REORDER_DI_TRACKS':
      return { ...state, diTracks: action.payload };

    // Amp actions
    case 'ADD_AMP':
      return { ...state, amps: [...state.amps, action.payload] };
    case 'REMOVE_AMP':
      return {
        ...state,
        amps: state.amps.filter((a) => a.id !== action.payload),
      };
    case 'REORDER_AMPS':
      return { ...state, amps: action.payload };

    // Cabinet actions
    case 'ADD_CAB':
      return { ...state, cabs: [...state.cabs, action.payload] };
    case 'REMOVE_CAB':
      return {
        ...state,
        cabs: state.cabs.filter((c) => c.id !== action.payload),
      };
    case 'REORDER_CABS':
      return { ...state, cabs: action.payload };

    // Effect actions
    case 'ADD_EFFECT':
      return { ...state, effects: [...state.effects, action.payload] };
    case 'REMOVE_EFFECT':
      return {
        ...state,
        effects: state.effects.filter((e) => e.id !== action.payload),
      };
    case 'REORDER_EFFECTS':
      return { ...state, effects: action.payload };

    // Reset
    case 'RESET':
      return initialBuilderState;

    default:
      return state;
  }
}

export interface BuilderActions {
  // DI Track actions
  addDITrack: (track: DIBlock) => void;
  removeDITrack: (id: string) => void;
  reorderDITracks: (tracks: DIBlock[]) => void;

  // Amp actions
  addAmp: (amp: AmpBlockData) => void;
  removeAmp: (id: string) => void;
  reorderAmps: (amps: AmpBlockData[]) => void;

  // Cabinet actions
  addCab: (cab: CabBlockData) => void;
  removeCab: (id: string) => void;
  reorderCabs: (cabs: CabBlockData[]) => void;

  // Effect actions
  addEffect: (effect: EffectBlockData) => void;
  removeEffect: (id: string) => void;
  reorderEffects: (effects: EffectBlockData[]) => void;

  // Reset
  reset: () => void;
}

export function useBuilderState(): [BuilderState, BuilderActions] {
  const [state, dispatch] = useReducer(builderReducer, initialBuilderState);

  const actions: BuilderActions = {
    // DI Track actions
    addDITrack: useCallback(
      (track: DIBlock) => dispatch({ type: 'ADD_DI_TRACK', payload: track }),
      []
    ),
    removeDITrack: useCallback(
      (id: string) => dispatch({ type: 'REMOVE_DI_TRACK', payload: id }),
      []
    ),
    reorderDITracks: useCallback(
      (tracks: DIBlock[]) => dispatch({ type: 'REORDER_DI_TRACKS', payload: tracks }),
      []
    ),

    // Amp actions
    addAmp: useCallback(
      (amp: AmpBlockData) => dispatch({ type: 'ADD_AMP', payload: amp }),
      []
    ),
    removeAmp: useCallback(
      (id: string) => dispatch({ type: 'REMOVE_AMP', payload: id }),
      []
    ),
    reorderAmps: useCallback(
      (amps: AmpBlockData[]) => dispatch({ type: 'REORDER_AMPS', payload: amps }),
      []
    ),

    // Cabinet actions
    addCab: useCallback(
      (cab: CabBlockData) => dispatch({ type: 'ADD_CAB', payload: cab }),
      []
    ),
    removeCab: useCallback(
      (id: string) => dispatch({ type: 'REMOVE_CAB', payload: id }),
      []
    ),
    reorderCabs: useCallback(
      (cabs: CabBlockData[]) => dispatch({ type: 'REORDER_CABS', payload: cabs }),
      []
    ),

    // Effect actions
    addEffect: useCallback(
      (effect: EffectBlockData) => dispatch({ type: 'ADD_EFFECT', payload: effect }),
      []
    ),
    removeEffect: useCallback(
      (id: string) => dispatch({ type: 'REMOVE_EFFECT', payload: id }),
      []
    ),
    reorderEffects: useCallback(
      (effects: EffectBlockData[]) =>
        dispatch({ type: 'REORDER_EFFECTS', payload: effects }),
      []
    ),

    // Reset
    reset: useCallback(() => dispatch({ type: 'RESET' }), []),
  };

  return [state, actions];
}
