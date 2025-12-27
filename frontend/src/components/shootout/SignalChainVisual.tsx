/**
 * SignalChainVisual - Displays the signal chain for a shootout.
 * Shows DI -> Amp Model -> Cabinet/IR flow.
 */

import type { ToneSelection } from '@/lib/api';
import { cn } from '@/lib/utils';

interface SignalChainVisualProps {
  segment: ToneSelection;
  className?: string;
}

// Block component for signal chain elements
interface ChainBlockProps {
  type: 'di' | 'amp' | 'cab' | 'effect';
  title: string;
  subtitle?: string;
  className?: string;
}

function ChainBlock({ type, title, subtitle, className }: ChainBlockProps) {
  const colorMap = {
    di: 'var(--color-block-di)',
    amp: 'var(--color-block-amp)',
    cab: 'var(--color-block-cab)',
    effect: 'var(--color-block-effect)',
  };

  const iconMap = {
    di: (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path fillRule="evenodd" d="M19.952 1.651a.75.75 0 01.298.599V16.303a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.403-4.909l2.311-.66a1.5 1.5 0 001.088-1.442V6.994l-9 2.572v9.737a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.402-4.909l2.31-.66a1.5 1.5 0 001.088-1.442V5.25a.75.75 0 01.544-.721l10.5-3a.75.75 0 01.658.122z" clipRule="evenodd" />
      </svg>
    ),
    amp: (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path fillRule="evenodd" d="M14.615 1.595a.75.75 0 01.359.852L12.982 9.75h7.268a.75.75 0 01.548 1.262l-10.5 11.25a.75.75 0 01-1.272-.71l1.992-7.302H3.75a.75.75 0 01-.548-1.262l10.5-11.25a.75.75 0 01.913-.143z" clipRule="evenodd" />
      </svg>
    ),
    cab: (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path d="M8.25 4.5a3.75 3.75 0 117.5 0v8.25a3.75 3.75 0 11-7.5 0V4.5z" />
        <path d="M6 10.5a.75.75 0 01.75.75v1.5a5.25 5.25 0 1010.5 0v-1.5a.75.75 0 011.5 0v1.5a6.751 6.751 0 01-6 6.709v2.291h3a.75.75 0 010 1.5h-7.5a.75.75 0 010-1.5h3v-2.291a6.751 6.751 0 01-6-6.709v-1.5A.75.75 0 016 10.5z" />
      </svg>
    ),
    effect: (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
        <path fillRule="evenodd" d="M12 6.75a5.25 5.25 0 016.775-5.025.75.75 0 01.313 1.248l-3.32 3.319c.063.475.276.934.641 1.299.365.365.824.578 1.3.64l3.318-3.319a.75.75 0 011.248.313 5.25 5.25 0 01-5.472 6.756c-1.018-.086-1.87.1-2.309.634L7.344 21.3A3.298 3.298 0 112.7 16.657l8.684-7.151c.533-.44.72-1.291.634-2.309A5.342 5.342 0 0112 6.75zM4.117 19.125a.75.75 0 01.75-.75h.008a.75.75 0 01.75.75v.008a.75.75 0 01-.75.75h-.008a.75.75 0 01-.75-.75v-.008z" clipRule="evenodd" />
      </svg>
    ),
  };

  return (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-3 rounded-lg border',
        className
      )}
      style={{
        borderColor: colorMap[type],
        backgroundColor: `color-mix(in srgb, ${colorMap[type]} 10%, transparent)`,
      }}
    >
      <div style={{ color: colorMap[type] }}>{iconMap[type]}</div>
      <div>
        <div className="font-medium text-[var(--color-text-primary)] text-sm">{title}</div>
        {subtitle && (
          <div className="text-xs text-[var(--color-text-muted)]">{subtitle}</div>
        )}
      </div>
    </div>
  );
}

// Arrow connector between blocks
function ChainArrow() {
  return (
    <div className="flex items-center justify-center w-8 flex-shrink-0">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="w-5 h-5 text-[var(--color-text-muted)]"
      >
        <path
          fillRule="evenodd"
          d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z"
          clipRule="evenodd"
        />
      </svg>
    </div>
  );
}

export function SignalChainVisual({ segment, className }: SignalChainVisualProps) {
  // Parse effects from JSON if present
  let effects: Array<{ effect_type: string; value: string }> = [];
  if (segment.effects_json) {
    try {
      effects = JSON.parse(segment.effects_json);
    } catch {
      // Ignore parse errors
    }
  }

  // Determine gear type icon
  const gearTypeLabel =
    segment.gear_type === 'amp'
      ? 'Amp Model'
      : segment.gear_type === 'pedal'
        ? 'Pedal'
        : segment.gear_type === 'full-rig'
          ? 'Full Rig'
          : 'Model';

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      {/* DI Input */}
      <ChainBlock type="di" title="DI Track" subtitle="Input" />
      <ChainArrow />

      {/* Highpass filter (if enabled) */}
      {segment.highpass && (
        <>
          <ChainBlock type="effect" title="80Hz Highpass" subtitle="Filter" />
          <ChainArrow />
        </>
      )}

      {/* Amp/Model */}
      <ChainBlock
        type="amp"
        title={segment.display_name ?? segment.tone_title}
        subtitle={`${gearTypeLabel} - ${segment.model_size}`}
      />

      {/* Cabinet/IR (if present) */}
      {segment.ir_path && (
        <>
          <ChainArrow />
          <ChainBlock
            type="cab"
            title={segment.ir_path.split('/').pop() ?? 'Cabinet IR'}
            subtitle="Impulse Response"
          />
        </>
      )}

      {/* Effects (if any) */}
      {effects.map((effect, index) => (
        <div key={index} className="contents">
          <ChainArrow />
          <ChainBlock
            type="effect"
            title={effect.effect_type.charAt(0).toUpperCase() + effect.effect_type.slice(1)}
            subtitle={effect.value}
          />
        </div>
      ))}
    </div>
  );
}

export default SignalChainVisual;
