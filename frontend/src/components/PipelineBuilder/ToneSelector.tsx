/**
 * ToneSelector - Browse and select tones from Tone 3000.
 */
import { useState, useMemo } from 'react';
import { Search, ChevronDown, Loader2, AlertCircle, Plus, Check } from 'lucide-react';
import { useMyTones, useFavoriteTones, useSearchTones } from './hooks';
import type { Tone, Gear, Platform } from '@/lib/api';
import { cn } from '@/lib/utils';

type ToneSource = 'mine' | 'favorites' | 'search';

interface ToneSelectorProps {
  selectedTones: Tone[];
  onSelect: (tone: Tone) => void;
  maxSelections?: number;
  className?: string;
}

const gearOptions: { value: Gear | ''; label: string }[] = [
  { value: '', label: 'All Gear' },
  { value: 'amp', label: 'Amps' },
  { value: 'full-rig', label: 'Full Rigs' },
  { value: 'pedal', label: 'Pedals' },
  { value: 'outboard', label: 'Outboard' },
  { value: 'ir', label: 'IRs' },
];

const platformOptions: { value: Platform | ''; label: string }[] = [
  { value: '', label: 'All Platforms' },
  { value: 'nam', label: 'NAM' },
  { value: 'ir', label: 'IR' },
  { value: 'aida-x', label: 'AIDA-X' },
];

export function ToneSelector({
  selectedTones,
  onSelect,
  maxSelections = 4,
  className,
}: ToneSelectorProps) {
  const [source, setSource] = useState<ToneSource>('mine');
  const [searchQuery, setSearchQuery] = useState('');
  const [gearFilter, setGearFilter] = useState<Gear | ''>('');
  const [platformFilter, setPlatformFilter] = useState<Platform | ''>('');

  // Fetch tones based on source
  const myTonesQuery = useMyTones(1, 50);
  const favoritesQuery = useFavoriteTones(1, 50);
  const searchTonesQuery = useSearchTones({
    query: searchQuery || undefined,
    gear: gearFilter || undefined,
    platform: platformFilter || undefined,
    per_page: 50,
  });

  // Get current data based on source
  const { data, isLoading, error } = useMemo(() => {
    switch (source) {
      case 'mine':
        return myTonesQuery;
      case 'favorites':
        return favoritesQuery;
      case 'search':
        return searchTonesQuery;
    }
  }, [source, myTonesQuery, favoritesQuery, searchTonesQuery]);

  const tones = data?.data ?? [];
  const selectedIds = new Set(selectedTones.map((t) => t.id));
  const canSelectMore = selectedTones.length < maxSelections;

  const handleToneClick = (tone: Tone) => {
    if (selectedIds.has(tone.id)) {
      return; // Already selected
    }
    if (!canSelectMore) {
      return; // Max selections reached
    }
    onSelect(tone);
  };

  return (
    <div className={cn('space-y-4', className)}>
      {/* Source tabs */}
      <div className="flex gap-2 border-b border-border">
        {(['mine', 'favorites', 'search'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSource(s)}
            className={cn(
              'border-b-2 px-4 py-2 text-sm font-medium transition-colors',
              source === s
                ? 'border-amber-500 text-amber-500'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            {s === 'mine' ? 'My Tones' : s === 'favorites' ? 'Favorites' : 'Search'}
          </button>
        ))}
      </div>

      {/* Search and filters (only for search tab) */}
      {source === 'search' && (
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search tones..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>
          <div className="flex gap-2">
            <div className="relative">
              <select
                value={gearFilter}
                onChange={(e) => setGearFilter(e.target.value as Gear | '')}
                className="h-10 appearance-none rounded-md border border-input bg-background pl-3 pr-8 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
              >
                {gearOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
            <div className="relative">
              <select
                value={platformFilter}
                onChange={(e) => setPlatformFilter(e.target.value as Platform | '')}
                className="h-10 appearance-none rounded-md border border-input bg-background pl-3 pr-8 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
              >
                {platformOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
          </div>
        </div>
      )}

      {/* Tone list */}
      <div className="min-h-[200px] rounded-lg border border-border bg-card/50">
        {isLoading ? (
          <div className="flex h-[200px] items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
            <AlertCircle className="h-6 w-6" />
            <p className="text-sm">{error.message}</p>
          </div>
        ) : tones.length === 0 ? (
          <div className="flex h-[200px] items-center justify-center text-muted-foreground">
            <p className="text-sm">
              {source === 'mine'
                ? 'No tones created yet'
                : source === 'favorites'
                  ? 'No favorites yet'
                  : 'No tones found'}
            </p>
          </div>
        ) : (
          <div className="max-h-[400px] divide-y divide-border overflow-y-auto">
            {tones.map((tone) => {
              const isSelected = selectedIds.has(tone.id);
              const isDisabled = !canSelectMore && !isSelected;

              return (
                <button
                  key={tone.id}
                  onClick={() => handleToneClick(tone)}
                  disabled={isSelected || isDisabled}
                  className={cn(
                    'flex w-full items-center gap-3 px-4 py-3 text-left transition-colors',
                    isSelected
                      ? 'bg-amber-500/10 text-amber-500'
                      : isDisabled
                        ? 'cursor-not-allowed opacity-50'
                        : 'hover:bg-muted/50'
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{tone.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {tone.platform.toUpperCase()} · {tone.gear.replace('-', ' ')}
                      {tone.makes.length > 0 && ` · ${tone.makes[0].name}`}
                    </p>
                  </div>
                  <div className="shrink-0">
                    {isSelected ? (
                      <Check className="h-5 w-5 text-amber-500" />
                    ) : (
                      <Plus className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Selection count */}
      <p className="text-sm text-muted-foreground">
        {selectedTones.length} of {maxSelections} tones selected
      </p>
    </div>
  );
}
