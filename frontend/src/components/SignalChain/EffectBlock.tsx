/**
 * EffectBlock - Signal chain block for audio effects/pedals.
 *
 * Supports various effect types with type-specific icons and parameters:
 * - EQ: Frequency bands and gain adjustments
 * - Delay: Time, feedback, and mix controls
 * - Reverb: Size, decay, and mix controls
 * - Compression: Threshold, ratio, and attack controls
 * - Noise Gate: Threshold control
 * - Boost: Gain amount control
 *
 * Uses purple accent color (--color-block-effect) via BlockCard.
 */
import {
  SlidersHorizontal,
  Timer,
  Waves,
  TrendingDown,
  DoorClosed,
  TrendingUp,
  X,
  type LucideIcon,
} from 'lucide-react';
import { BlockCard } from './BlockCard';
import { cn } from '@/lib/utils';

/**
 * Supported effect types with their visual and parameter configurations.
 */
export type EffectType = 'eq' | 'delay' | 'reverb' | 'compression' | 'noise-gate' | 'boost';

/**
 * Effect parameter value - can be a number or percentage string.
 */
export type EffectParamValue = number | string;

/**
 * Effect parameters vary by effect type.
 */
export interface EQParams {
  lowGain?: number;      // dB (-12 to +12)
  midGain?: number;      // dB (-12 to +12)
  highGain?: number;     // dB (-12 to +12)
  lowFreq?: number;      // Hz
  midFreq?: number;      // Hz
  highFreq?: number;     // Hz
}

export interface DelayParams {
  time?: number;         // ms (0-2000)
  feedback?: number;     // percentage (0-100)
  mix?: number;          // percentage (0-100)
}

export interface ReverbParams {
  size?: number;         // percentage (0-100)
  decay?: number;        // seconds (0-10)
  mix?: number;          // percentage (0-100)
}

export interface CompressionParams {
  threshold?: number;    // dB (-60 to 0)
  ratio?: number;        // ratio (1:1 to 20:1)
  attack?: number;       // ms (0-100)
  release?: number;      // ms (0-1000)
}

export interface NoiseGateParams {
  threshold?: number;    // dB (-80 to 0)
}

export interface BoostParams {
  gain?: number;         // dB (0-24)
}

/**
 * Union type for all effect parameters.
 */
export type EffectParams =
  | EQParams
  | DelayParams
  | ReverbParams
  | CompressionParams
  | NoiseGateParams
  | BoostParams;

interface EffectBlockProps {
  /** The type of effect */
  effectType: EffectType;
  /** Display name for the effect (e.g., "Studio EQ", "Tape Delay") */
  name: string;
  /** Effect parameters (varies by effect type) */
  params?: EffectParams;
  /** Whether the effect is bypassed/disabled */
  bypassed?: boolean;
  /** Callback when the block is removed */
  onRemove?: () => void;
  /** Optional click handler for the block */
  onClick?: () => void;
  /** Whether the block is selected/active */
  isSelected?: boolean;
  /** Show drag handle for reordering */
  showDragHandle?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Drag handle props for dnd-kit integration */
  dragHandleProps?: Record<string, unknown>;
}

/**
 * Maps effect types to their display labels.
 */
const effectTypeLabels: Record<EffectType, string> = {
  eq: 'EQ',
  delay: 'Delay',
  reverb: 'Reverb',
  compression: 'Compressor',
  'noise-gate': 'Noise Gate',
  boost: 'Boost',
};

/**
 * Maps effect types to their icons.
 */
const effectTypeIcons: Record<EffectType, LucideIcon> = {
  eq: SlidersHorizontal,
  delay: Timer,
  reverb: Waves,
  compression: TrendingDown,
  'noise-gate': DoorClosed,
  boost: TrendingUp,
};

/**
 * Formats a parameter value for display.
 */
function formatParamValue(value: number | undefined, unit: string, decimals = 0): string {
  if (value === undefined) return '--';
  return `${value.toFixed(decimals)}${unit}`;
}

/**
 * Formats a ratio value (e.g., "4:1").
 */
function formatRatio(value: number | undefined): string {
  if (value === undefined) return '--';
  return `${value}:1`;
}

/**
 * Renders parameters for EQ effect.
 */
function EQParameters({ params }: { params?: EQParams }) {
  if (!params) return null;

  return (
    <div className="grid grid-cols-3 gap-2 text-xs">
      <div className="space-y-1">
        <span className="text-muted-foreground">Low</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.lowGain, 'dB')}
        </p>
      </div>
      <div className="space-y-1">
        <span className="text-muted-foreground">Mid</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.midGain, 'dB')}
        </p>
      </div>
      <div className="space-y-1">
        <span className="text-muted-foreground">High</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.highGain, 'dB')}
        </p>
      </div>
    </div>
  );
}

/**
 * Renders parameters for Delay effect.
 */
function DelayParameters({ params }: { params?: DelayParams }) {
  if (!params) return null;

  return (
    <div className="grid grid-cols-3 gap-2 text-xs">
      <div className="space-y-1">
        <span className="text-muted-foreground">Time</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.time, 'ms')}
        </p>
      </div>
      <div className="space-y-1">
        <span className="text-muted-foreground">Feedback</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.feedback, '%')}
        </p>
      </div>
      <div className="space-y-1">
        <span className="text-muted-foreground">Mix</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.mix, '%')}
        </p>
      </div>
    </div>
  );
}

/**
 * Renders parameters for Reverb effect.
 */
function ReverbParameters({ params }: { params?: ReverbParams }) {
  if (!params) return null;

  return (
    <div className="grid grid-cols-3 gap-2 text-xs">
      <div className="space-y-1">
        <span className="text-muted-foreground">Size</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.size, '%')}
        </p>
      </div>
      <div className="space-y-1">
        <span className="text-muted-foreground">Decay</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.decay, 's', 1)}
        </p>
      </div>
      <div className="space-y-1">
        <span className="text-muted-foreground">Mix</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.mix, '%')}
        </p>
      </div>
    </div>
  );
}

/**
 * Renders parameters for Compression effect.
 */
function CompressionParameters({ params }: { params?: CompressionParams }) {
  if (!params) return null;

  return (
    <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
      <div className="space-y-1">
        <span className="text-muted-foreground">Threshold</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.threshold, 'dB')}
        </p>
      </div>
      <div className="space-y-1">
        <span className="text-muted-foreground">Ratio</span>
        <p className="font-medium text-foreground">
          {formatRatio(params.ratio)}
        </p>
      </div>
      <div className="space-y-1">
        <span className="text-muted-foreground">Attack</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.attack, 'ms')}
        </p>
      </div>
      <div className="space-y-1">
        <span className="text-muted-foreground">Release</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.release, 'ms')}
        </p>
      </div>
    </div>
  );
}

/**
 * Renders parameters for Noise Gate effect.
 */
function NoiseGateParameters({ params }: { params?: NoiseGateParams }) {
  if (!params) return null;

  return (
    <div className="text-xs">
      <div className="space-y-1">
        <span className="text-muted-foreground">Threshold</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.threshold, 'dB')}
        </p>
      </div>
    </div>
  );
}

/**
 * Renders parameters for Boost effect.
 */
function BoostParameters({ params }: { params?: BoostParams }) {
  if (!params) return null;

  return (
    <div className="text-xs">
      <div className="space-y-1">
        <span className="text-muted-foreground">Gain</span>
        <p className="font-medium text-foreground">
          {formatParamValue(params.gain, 'dB')}
        </p>
      </div>
    </div>
  );
}

/**
 * Renders the appropriate parameters component based on effect type.
 */
function EffectParameters({
  effectType,
  params,
}: {
  effectType: EffectType;
  params?: EffectParams;
}) {
  if (!params) return null;

  switch (effectType) {
    case 'eq':
      return <EQParameters params={params as EQParams} />;
    case 'delay':
      return <DelayParameters params={params as DelayParams} />;
    case 'reverb':
      return <ReverbParameters params={params as ReverbParams} />;
    case 'compression':
      return <CompressionParameters params={params as CompressionParams} />;
    case 'noise-gate':
      return <NoiseGateParameters params={params as NoiseGateParams} />;
    case 'boost':
      return <BoostParameters params={params as BoostParams} />;
    default:
      return null;
  }
}

export function EffectBlock({
  effectType,
  name,
  params,
  bypassed = false,
  onRemove,
  onClick,
  isSelected = false,
  showDragHandle = false,
  className,
  dragHandleProps,
}: EffectBlockProps) {
  const Icon = effectTypeIcons[effectType];
  const typeLabel = effectTypeLabels[effectType];

  // Build content for the BlockCard
  const content = (
    <div className="space-y-3">
      {/* Effect type badge */}
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
            'bg-purple-500/20 text-purple-400 border-purple-500/30'
          )}
        >
          {typeLabel}
        </span>
        {bypassed && (
          <span className="inline-flex items-center rounded-full border border-muted-foreground/30 bg-muted/50 px-2 py-0.5 text-xs text-muted-foreground">
            Bypassed
          </span>
        )}
      </div>

      {/* Parameters display */}
      <EffectParameters effectType={effectType} params={params} />
    </div>
  );

  // If using click handler and onRemove, wrap in clickable div
  if (onClick || onRemove) {
    return (
      <div
        className={cn(
          'relative',
          onClick && 'cursor-pointer',
          bypassed && 'opacity-50',
          className
        )}
        onClick={onClick}
        role={onClick ? 'button' : undefined}
        tabIndex={onClick ? 0 : undefined}
        onKeyDown={
          onClick
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onClick();
                }
              }
            : undefined
        }
      >
        {/* Remove button */}
        {onRemove && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            className="absolute right-2 top-2 z-10 rounded-full p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
            aria-label={`Remove ${name}`}
          >
            <X className="h-4 w-4" />
          </button>
        )}
        <BlockCard
          type="effect"
          icon={<Icon className="h-5 w-5" />}
          title={name}
          subtitle="Effect"
          showDragHandle={showDragHandle}
          dragHandleProps={dragHandleProps}
          className={cn(
            isSelected && 'ring-1 ring-purple-500/50 border-purple-500'
          )}
        >
          {content}
        </BlockCard>
      </div>
    );
  }

  // Simple display mode (no click handler)
  return (
    <BlockCard
      type="effect"
      icon={<Icon className="h-5 w-5" />}
      title={name}
      subtitle="Effect"
      showDragHandle={showDragHandle}
      dragHandleProps={dragHandleProps}
      className={cn(bypassed && 'opacity-50', className)}
    >
      {content}
    </BlockCard>
  );
}
