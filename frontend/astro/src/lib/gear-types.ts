/**
 * Shared gear type constants and mappings.
 * Used by both browse and my-gear views for consistent filtering.
 */

import type { Gear, GearItemType } from './api';

/**
 * Gear type configuration with colors and labels.
 * Used for filter buttons and display.
 */
export interface GearTypeConfig {
  value: Gear;
  label: string;
  color: string;
  bgColor: string;
}

export const GEAR_TYPES: GearTypeConfig[] = [
  { value: 'amp', label: 'Amps', color: 'var(--color-block-amp)', bgColor: '#2D1810' },
  { value: 'pedal', label: 'Pedals', color: 'var(--color-block-effect)', bgColor: '#1D2D10' },
  { value: 'ir', label: 'IRs', color: 'var(--color-block-cab)', bgColor: '#10202D' },
  { value: 'full-rig', label: 'Full Rigs', color: 'var(--color-block-amp)', bgColor: '#2D1810' },
  { value: 'outboard', label: 'Outboard', color: 'var(--color-block-effect)', bgColor: '#1D2D10' },
];

/**
 * Map frontend Gear type to backend GearItemType.
 * Frontend uses hyphenated values (e.g., 'full-rig'), backend uses underscores (e.g., 'full_rig').
 */
export function gearToGearItemType(gear: Gear): GearItemType {
  switch (gear) {
    case 'amp':
      return 'amp';
    case 'pedal':
      return 'pedal';
    case 'ir':
      return 'ir';
    case 'full-rig':
      return 'full_rig';
    case 'outboard':
      return 'post_effect';
    default:
      return 'pedal';
  }
}

/**
 * Map backend GearItemType to frontend Gear type.
 * Backend uses underscores (e.g., 'full_rig'), frontend uses hyphenated values (e.g., 'full-rig').
 */
export function gearItemTypeToGear(gearType: GearItemType): Gear | null {
  switch (gearType) {
    case 'amp':
      return 'amp';
    case 'pedal':
      return 'pedal';
    case 'ir':
      return 'ir';
    case 'full_rig':
      return 'full-rig';
    case 'post_effect':
      return 'outboard';
    default:
      return null;
  }
}

/**
 * Get gear type configuration by value.
 */
export function getGearTypeConfig(gear: Gear): GearTypeConfig | undefined {
  return GEAR_TYPES.find((t) => t.value === gear);
}

/**
 * Get gear type label (short form for filter buttons).
 */
export function getGearTypeLabel(gear: Gear): string {
  const config = getGearTypeConfig(gear);
  return config?.label || gear;
}

/**
 * Get gear type full description.
 */
export function getGearTypeFullLabel(gear: Gear): string {
  switch (gear) {
    case 'amp':
      return 'Amp Head Capture';
    case 'pedal':
      return 'Pedal Capture';
    case 'ir':
      return 'Impulse Response';
    case 'full-rig':
      return 'Full Rig / Combo Capture';
    case 'outboard':
      return 'Outboard Capture';
    default:
      return gear;
  }
}

/**
 * Get gear type background color for placeholder images.
 */
export function getGearTypeBgColor(gear: Gear): string {
  const config = getGearTypeConfig(gear);
  return config?.bgColor || '#1a1a2e';
}
