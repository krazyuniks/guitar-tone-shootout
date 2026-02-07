/**
 * WaveformDisplay - Renders audio waveform visualization from peak data.
 *
 * Accepts base64-encoded Float32Array (200 values, 0-1 range) and renders
 * as SVG with configurable dimensions and colors.
 *
 * Uses design tokens:
 * - --color-block-di for waveform color
 */
import { useMemo } from 'react';

interface WaveformDisplayProps {
  /** Base64-encoded waveform data (Float32Array, 200 values, 0-1 range) */
  waveformData: string;
  /** Width in pixels (default: 100%) */
  width?: number | string;
  /** Height in pixels (default: 48) */
  height?: number;
  /** CSS color for the waveform (default: uses --color-block-di) */
  color?: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Decodes base64-encoded Float32Array.
 */
function decodeWaveformData(base64: string): Float32Array {
  try {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return new Float32Array(bytes.buffer);
  } catch {
    // Return empty array on decode error
    return new Float32Array(0);
  }
}

/**
 * Generates SVG path data for waveform visualization.
 * Creates a mirrored waveform (peaks extend both up and down from center).
 */
function generateWaveformPath(
  peaks: Float32Array,
  width: number,
  height: number
): string {
  if (peaks.length === 0) {
    return '';
  }

  const centerY = height / 2;
  const barWidth = width / peaks.length;
  const maxAmplitude = centerY * 0.9; // Leave 10% padding

  // Build path data for filled area
  const points: string[] = [];

  // Top half of waveform (going left to right)
  for (let i = 0; i < peaks.length; i++) {
    const x = i * barWidth + barWidth / 2;
    const amplitude = peaks[i] * maxAmplitude;
    const y = centerY - amplitude;
    if (i === 0) {
      points.push(`M ${x} ${centerY}`);
      points.push(`L ${x} ${y}`);
    } else {
      points.push(`L ${x} ${y}`);
    }
  }

  // Bottom half of waveform (going right to left, mirrored)
  for (let i = peaks.length - 1; i >= 0; i--) {
    const x = i * barWidth + barWidth / 2;
    const amplitude = peaks[i] * maxAmplitude;
    const y = centerY + amplitude;
    points.push(`L ${x} ${y}`);
  }

  points.push('Z'); // Close the path
  return points.join(' ');
}

export function WaveformDisplay({
  waveformData,
  width = '100%',
  height = 48,
  color,
  className = '',
}: WaveformDisplayProps) {
  // Decode and memoize waveform data
  const peaks = useMemo(() => decodeWaveformData(waveformData), [waveformData]);

  // Use a fixed internal width for path calculation, SVG will scale
  const internalWidth = 400;
  const pathData = useMemo(
    () => generateWaveformPath(peaks, internalWidth, height),
    [peaks, height]
  );

  // If no valid data, show placeholder
  if (peaks.length === 0) {
    return (
      <div
        className={`flex items-center justify-center rounded bg-[var(--color-block-di)]/5 ${className}`}
        style={{ width, height }}
      >
        <span className="text-xs text-muted-foreground">No waveform data</span>
      </div>
    );
  }

  const fillColor = color || 'var(--color-block-di)';

  return (
    <svg
      viewBox={`0 0 ${internalWidth} ${height}`}
      preserveAspectRatio="none"
      className={`rounded ${className}`}
      style={{
        width,
        height,
        backgroundColor: 'color-mix(in srgb, var(--color-block-di) 5%, transparent)',
      }}
    >
      <path
        d={pathData}
        fill={fillColor}
        fillOpacity={0.4}
        stroke={fillColor}
        strokeWidth={0.5}
        strokeOpacity={0.6}
      />
    </svg>
  );
}
