/**
 * ToneCard - Displays a selected tone with removal option.
 */
import { X, Music, Zap, Speaker, Mic } from 'lucide-react';
import type { Tone, Gear, Platform } from '@/lib/api';
import { cn } from '@/lib/utils';

interface ToneCardProps {
  tone: Tone;
  onRemove?: () => void;
  className?: string;
}

const gearIcons: Record<Gear, typeof Music> = {
  amp: Speaker,
  'full-rig': Zap,
  pedal: Music,
  outboard: Mic,
  ir: Music,
};

const platformColors: Record<Platform, string> = {
  nam: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  ir: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'aida-x': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

const platformLabels: Record<Platform, string> = {
  nam: 'NAM',
  ir: 'IR',
  'aida-x': 'AIDA-X',
};

export function ToneCard({ tone, onRemove, className }: ToneCardProps) {
  const GearIcon = gearIcons[tone.gear] ?? Music;

  return (
    <div
      className={cn(
        'relative rounded-lg border border-border bg-card p-4 transition-colors hover:border-amber-500/50',
        className
      )}
    >
      {onRemove && (
        <button
          onClick={onRemove}
          className="absolute right-2 top-2 rounded-full p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
          aria-label={`Remove ${tone.title}`}
        >
          <X className="h-4 w-4" />
        </button>
      )}

      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-muted">
          <GearIcon className="h-5 w-5 text-amber-500" />
        </div>

        <div className="min-w-0 flex-1">
          <h4 className="truncate font-medium text-foreground">{tone.title}</h4>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
                platformColors[tone.platform]
              )}
            >
              {platformLabels[tone.platform]}
            </span>
            <span className="text-xs capitalize text-muted-foreground">
              {tone.gear.replace('-', ' ')}
            </span>
          </div>
          {tone.makes.length > 0 && (
            <p className="mt-1 truncate text-xs text-muted-foreground">
              {tone.makes.map((m) => m.name).join(', ')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
